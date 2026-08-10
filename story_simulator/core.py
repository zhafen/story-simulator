"""The event-driven simulation kernel: everything that makes story-simulator's
MCP tools possible, session state included -- `mcp_server.py` only wires this
up to the MCP protocol (`@server.tool()` functions that unpack `Context` into
a plain session id and call straight into here).

Historically stayed framework-agnostic on purpose ("works with nothing
layered on top"); that constraint no longer holds now that responders
(`story_simulator.config.event_responder`, `story_simulator.resolve`) are
central to how this project works, not an optional layer on top of it -- so
this module absorbed the bulk of `mcp_server.py`'s own implementation rather
than staying a small Context-free base. Splitting pieces back out (e.g. if a
second host protocol besides MCP ever needs this logic) is still open to do
later, as needed.
"""

from __future__ import annotations

__iacs__ = {
    "todo": (
        "The pop/is_event_valid/advance_clock/predict_next_event/push_event "
        "functions just live loose at module scope here. Evaluate whether "
        "the event loop deserves a more deliberate structure (a class, a "
        "dataclass-based state object, an explicit stage protocol) as more "
        "modules start hooking into it, instead of a flat function bag."
    ),
    "solution of": "story_simulator_mission.stateless_client",
}

import base64
import json
import shutil
import subprocess
import time
import urllib.parse
import weakref
from pathlib import Path

import pandas as pd
import psycopg
import psycopg.sql
import yaml
from iacs.registrar import Registrar

from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    MANIFEST_DIR,
    WORLD_FILE_ID,
    event_responder,
    registry_schema_name,
    registry_url,
    resolve_database_dsn,
)
from story_simulator.resolve import JudgmentRequest, NeedsExternalInput, TurnReplay

# save_dir's two export subdirectories, each holding one EC yaml file per
# original source (currently always one, since every registrar.update() call
# shares WORLD_FILE_ID as its source key -- see that constant's comment) --
# directories, not fixed filenames, so a save can be split across as many
# files as its author wants, matching iacs's own entity-file organization
# freedom, and the loader (see start_world) just recurses into whichever one
# it picks rather than assuming a single file.
WORLD_DIRNAME = WORLD_FILE_ID
WORLD_HISTORY_DIRNAME = "world_history"

_registrars: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_save_dirs: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# World time (seconds since world creation), per session -- set in
# process_event from the popped entity's own `next_due` (see
# advance_clock: "the popped entity's own next_due becomes 'now' for this
# turn") and read by _next_time_stamp for every write anything does while
# resolving that entity's turn, so "how recent is this row" and "when is X
# next due" share one clock instead of the wall clock. Session-scoped
# process memory, not persisted -- a subprocess restart mid-turn resets it
# to 0.0 until the next entity pop re-derives it, a known gap (see
# docs/manifest/story-simulator.yaml: world_time_concept) accepted for now
# in favor of not introducing a separate persisted clock entity.
_current_world_time: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

# It's how a base-module event tells the loop it's done (see
# resolve_event's default=inf) when the next_due_in line is omitted,
# not a mistake to fall back from with a hardcoded interval.
_NEXT_DUE_IN_INSTRUCTION = (
    "If there's more to happen, end your answer with a line formatted "
    "exactly as `next_due_in: <seconds>` stating how long from now. Omit "
    "that line entirely if this is finished and shouldn't happen again."
)


def merge_yaml_string(registrar: Registrar, yaml_text: str, time: float | None = None) -> None:
    """Run the ETL pipeline on a raw YAML string and merge the result into `registrar`.

    Same mechanism every write in this project uses.
    `time`, when given, backfills the time_dimension field the merged data
    declares (world time, seconds since world creation) so `Registry.view_current` can
    resolve which of an entity's accumulated rows is current.
    """
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text}, time=time)


def safe_view(registrar: Registrar, fields: str | list[str]) -> pd.DataFrame | None:
    """Execute `registrar.view(fields)`, or None if that component type isn't loaded yet."""
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view(fields).execute()
    except KeyError:
        return None


def safe_view_current(registrar: Registrar, fields: str | list[str]) -> pd.DataFrame | None:
    """Like `safe_view`, but resolves each field's current row per entity.

    Uses `registrar.view_current`.  A component type with no `time_dimension` field
    behaves exactly like `safe_view` (every row is "current").
    """
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view_current(fields).execute()
    except KeyError:
        return None


# ---------------------------------------------------------------------------
# Event-driven simulation loop -- one function per box in the turn-anatomy
# diagram (see docs/architecture.md). Schedule lives as registry data (a
# `next_due` component), not an in-memory priority queue.
# ---------------------------------------------------------------------------


def due_by_entity(registrar: Registrar) -> pd.DataFrame:
    """One row per entity with a next_due of its own: `entity_id`, `due` (float).

    Casts explicitly to `next_due.value: float`: a save with zero
    `next_due` rows anywhere leaves the schema undeclared on a plain
    `Registrar.load()` reconnect, so `get` falls back to a generic string
    table that can't be compared against a float.
    """
    return (
        registrar.get("next_due")
        .group_by("entity_id")
        .aggregate(due=lambda t: t["value"].cast("float64").max())
        .execute()
    )


def pop_event(registrar: Registrar) -> str | None:
    """Pop event box: whichever entity, of any kind, is due soonest, or
    None if nothing is currently scheduled.

    Logic is fully separated from any dependence on how the events are
    resolved. An entity with no `next_due` row simply isn't a candidate
    (not sorted as due immediately): an entity only enters the schedule
    once something explicitly pushes it there (see `push_event`).
    An entity most recently pushed at `due_at=inf` is treated as
    permanently done, filtered out the same way -- see `resolve_event`.

    A plain read, not a destructive dequeue -- `story_simulator.resolve`'s
    replay-from-the-top mechanism depends on calling this again and again
    being safe.
    """
    if "next_due" not in registrar.registry.component_types:
        return None
    due_df = registrar.view_current("next_due.value").execute()
    due_df = due_df[due_df["next_due.value"] < float("inf")]
    if due_df.empty:
        return None
    return due_df.sort_values("next_due.value").iloc[0]["entity_id.alias"]


def is_event_valid(registrar: Registrar, alias: str) -> bool:
    """Valid? box: is `alias` still a real, eligible entity.

    Always true today by construction -- `pop_event` re-reads current
    state fresh rather than pre-computing events into a queue, so the
    staleness problem this check exists for doesn't arise yet. Seam for a
    future lookahead/precomputed-event design to extend.
    """
    return registrar.get_entity_id(alias) is not None


def advance_clock(registrar: Registrar, alias: str) -> float:
    """Advance clock box: the popped entity's own `next_due` becomes "now" for this turn.

    No separate persisted global clock -- the popped event's own timestamp
    is the only notion of "current time" needed today.
    """
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return 0.0
    due_df = due_by_entity(registrar)
    match = due_df[due_df["entity_id"] == entity_id]
    return float(match.iloc[0]["due"]) if not match.empty else 0.0


def predict_next_event(registrar: Registrar, alias: str, next_due_in: float) -> float:
    """Predict next event / Predict next box: compute when `alias` should next be due.

    Named for what the result actually is -- the event `alias`'s current
    resolution causes to happen next -- rather than the more generic
    "predict an event" `predict_event` used to read as.

    Serves both call sites (initial per-entity setup and the
    post-`Process event` reschedule) -- same computation either way.
    Pure: doesn't write anything itself.
    """
    now = advance_clock(registrar, alias)
    return now + next_due_in


def push_event(registrar: Registrar, alias: str, due_at: float, time: float | None = None) -> None:
    """Push to queue / Push events box: commit `alias`'s next_due to the registry.

    Writing `next_due` IS "pushing to the queue" -- there's no separate
    in-memory priority queue; `pop_event`'s live registry read *is* the
    queue. `time` should get the same world-time stamp every other
    time_dimension'd write uses, since `next_due.time` needs it to resolve
    which row is current for an entity rescheduled more than once.
    """
    data = {f"{alias}_next_due": [{"same_as": {"value": alias}}, {"next_due": {"value": due_at}}]}
    merge_yaml_string(registrar, yaml.safe_dump(data, sort_keys=False), time=time)


# ---------------------------------------------------------------------------
# Session state -- looked up by `session`, an opaque, weak-referenceable
# object (`ctx.request_context.session` from mcp_server.py's MCP `Context`,
# but nothing here depends on that type specifically).
# ---------------------------------------------------------------------------


def _get_registrar(session) -> Registrar:
    """Return this session's open world Registrar, or raise a clear error if none is open."""
    if session not in _registrars:
        raise ValueError("No world open for this session yet — call start_world first.")
    return _registrars[session]


def _get_save_dir(session) -> Path:
    return _save_dirs[session]


def _next_time_stamp(session) -> float:
    """The world-time stamp for `position.time` and friends: this session's
    current in-fiction "now" (seconds since world creation).

    Reads `_current_world_time`, set in `process_event` from the popped
    entity's own `next_due` (see `advance_clock`) -- every write made
    while resolving one entity's turn shares that same "now", the same
    world-time axis `next_due.value` itself uses, rather than a wall-clock
    substitute. Falls back to 0.0 if nothing has been popped yet for this
    session (e.g. a stray `update_registry` call before `advance_simulation`
    is ever run).

    Two writes at the same world time -- several update_registry calls
    resolving one turn, or any number of stray calls before the first event
    is ever popped -- used to need a tie-break nudge handed out here,
    since `Registry.view_current`'s own tie handling was arbitrary. iacs's
    own `_seq` write-order column (zhafen/iacs#94) is merged now, so
    "most recent write wins" at a tied world time is iacs's own guarantee
    to keep -- not something this function needs to fake by nudging the
    stamp itself.
    """
    return _current_world_time.get(session, 0.0)


def _yaml_files(directory: Path) -> list[Path]:
    """All *.yaml/*.yml files under `directory`, recursed into, sorted for determinism."""
    return sorted(f for pattern in ("*.yaml", "*.yml") for f in directory.rglob(pattern))


def _seed_save_dir(save_dir: Path, scenario_dir: Path) -> None:
    """Copy a starting scenario's save data into a brand-new, still-empty save_dir."""
    if save_dir.resolve() == scenario_dir.resolve():
        return
    if any(save_dir.iterdir()):
        return
    shutil.copytree(scenario_dir, save_dir, dirs_exist_ok=True)


# ---------------------------------------------------------------------------
# Postgres dev-convenience bootstrap -- the one Postgres-specific corner of
# this module; everywhere else talks to the registry database only through
# `config.registry_url`/`Registrar`, which stay backend-agnostic via
# `ibis.connect`.
# ---------------------------------------------------------------------------


def _is_local_dsn(dsn: str) -> bool:
    """True if `dsn` points at this machine, where auto-starting a server is safe."""
    return urllib.parse.urlparse(dsn).hostname in ("localhost", "127.0.0.1", "::1", None)


def _can_connect(dsn: str) -> str | None:
    """Try connecting to `dsn`; return None on success or the error text on failure."""
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            return None
    except psycopg.OperationalError as exc:
        return str(exc)


def _start_local_postgres() -> None:
    """Best-effort start of a local `postgresql` service, for dev convenience.

    Only ever called on a localhost DSN that just failed with a
    connection-refused error (see `_ensure_postgres_running`) -- never
    manages a remote server. Tries whichever service-control command this
    install actually has; silently no-ops if neither is found; either way,
    the caller's own follow-up connection attempt is what determines success.
    """
    for cmd in (["service", "postgresql", "start"], ["pg_ctlcluster", "16", "main", "start"]):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue


def _ensure_default_dev_password() -> None:
    """Set the local `postgres` role's password to match the documented default DSN.

    Only reached from `_ensure_postgres_running` after *this call* just
    started a previously-unreachable local server and it's rejecting the
    default DSN's password -- i.e. a brand-new cluster whose `postgres` role
    has no password set yet, not a pre-existing, deliberately configured
    server. Runs the ALTER as the `postgres` OS/DB user over the Unix
    socket (peer-authenticated, so no password needed for this step itself),
    the same way a human operator would from the shell.
    """
    alter_sql = "ALTER USER postgres WITH PASSWORD 'postgres';"
    for cmd in (
        ["sudo", "-u", "postgres", "psql", "-c", alter_sql],
        ["su", "postgres", "-c", f"psql -c \"{alter_sql}\""],
    ):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=15)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue


def _ensure_postgres_running() -> None:
    """Make sure the registry database is reachable, starting a local one if not.

    Dev convenience only: intervenes solely for a localhost DSN whose server
    isn't listening at all (connection refused), which is the "nobody has
    started Postgres in this environment yet" case. Any other failure --
    including a *reachable* server rejecting these credentials, which could
    mean a deliberately different local password -- is left to surface via
    `_ensure_postgres_schema`'s own connection attempt rather than papered
    over here.
    """
    __iacs__ = {"solution of": "story_simulator_mission.dev_db_bootstrap"}
    dsn = resolve_database_dsn()
    if not _is_local_dsn(dsn):
        return

    error = _can_connect(dsn)
    if error is None or "refused" not in error:
        return

    _start_local_postgres()
    for _ in range(10):
        time.sleep(1)
        error = _can_connect(dsn)
        if error is None:
            return
        if "password authentication failed" in error:
            _ensure_default_dev_password()
            if _can_connect(dsn) is None:
                return
            break
    # Give up quietly; _ensure_postgres_schema's own connect will raise a
    # clear error if the server still isn't usable.


def _ensure_postgres_schema(save_dir: Path) -> None:
    """Create `save_dir`'s registry schema if it doesn't exist yet.

    `CREATE SCHEMA` is a one-off admin statement against the database, not
    registry data, so it's a plain psycopg connection rather than something
    routed through `Registrar`/`ibis`. Has to run before `Registrar.load`
    ever connects with that schema name: an unknown schema in a
    connection's search_path fails silently rather than erroring (see
    `config.registry_url`).
    """
    schema = registry_schema_name(save_dir)
    with psycopg.connect(resolve_database_dsn(), autocommit=True) as con:
        con.execute(
            psycopg.sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                psycopg.sql.Identifier(schema)
            )
        )


# ---------------------------------------------------------------------------
# World save I/O
# ---------------------------------------------------------------------------


def _export_world_yaml(registrar: Registrar, save_dir: Path) -> None:
    """Re-export the registry's state to `save_dir`'s `world/`/`world_history/` dirs.

    A straight, mechanical round-trip (`Registrar.export_manifest`) -- not
    the old `IacsArchivist`'s LLM-driven read/write loop, removed along with
    `EnsembleWorld`/`Interpreter` in the MCP rebuild (see
    docs/manifest/history.yaml: project_history.turn_pipeline_removed and
    .world_yaml_sync_reverses_old_archivist_design). Runs after every
    registry write so a save's own YAML stops being frozen turn-zero seed
    data and instead reads as a live mirror of the registry, which stays the
    actual source of truth.

    Writes to two directories, not one:
    - `world/`: current state (the default, collapsed export -- a
      time_dimension'd component type like `description`/`state`/`position`
      shows only its current row per entity, not every historical
      restatement).
    - `world_history/`: the same content, uncollapsed -- every row ever
      recorded, full change history. Kept because the registry itself still
      accumulates full history forever (nothing here is deleted, only what
      the *collapsed* export shows), but that history would otherwise only
      ever exist in this process's own database connection -- worth having
      committed alongside the save, not just inferable from it.

    Each is a directory, not a single fixed filename, so a save can be
    split across more files later without a format change, matching
    iacs's own principle of letting an EC source be organized across as
    many files as its author wants -- `start_world`'s loader recurses
    into whichever directory it picks rather than assuming one file lives
    there. An earlier revision used fixed filenames instead; see
    docs/manifest/history.yaml:
    project_history.world_save_format_switched_from_fixed_filenames_to_directories
    for why that changed.

    `export_manifest` also re-exports this project's own field-schema
    manifest (merged into every registry via `input_dirs=[MANIFEST_DIR]`)
    to its own `builtins.yaml` alongside `world.yaml` -- that's just a
    normalized round-trip of `manifest/builtins.yaml`'s static content, not
    game state, so it's deleted rather than left to accumulate confusingly
    in each export directory.
    """
    __iacs__ = {"solution of": "story_simulator_mission.seed_yaml_reflects_live_state"}
    world_dir = save_dir / WORLD_DIRNAME
    world_yaml = world_dir / f"{WORLD_FILE_ID}.yaml"
    for path in registrar.export_manifest(output_dir=str(world_dir)):
        if Path(path) != world_yaml:
            Path(path).unlink(missing_ok=True)

    world_history_dir = save_dir / WORLD_HISTORY_DIRNAME
    world_history_yaml = world_history_dir / f"{WORLD_FILE_ID}.yaml"
    for path in registrar.export_manifest(
        output_dir=str(world_history_dir), collapse_time_dimension=False
    ):
        if Path(path) != world_history_yaml:
            Path(path).unlink(missing_ok=True)


def _update_registry_and_sync(registrar: Registrar, save_dir: Path, yaml_string: str, session) -> None:
    """Merge `yaml_string` into the registry, then sync `save_dir`'s YAML to match."""
    registrar.update(
        input_dirs=[str(MANIFEST_DIR)],
        yaml_strings={WORLD_FILE_ID: yaml_string},
        time=_next_time_stamp(session),
    )
    _export_world_yaml(registrar, save_dir)


# ---------------------------------------------------------------------------
# Turn resolution
# ---------------------------------------------------------------------------


def _parse_next_due_in(answer: str, default: float = 1.0) -> tuple[str, float]:
    """Split a resolve_event answer into (narration, next_due_in).

    Looks for a trailing `next_due_in: <seconds>` line (see
    `_NEXT_DUE_IN_INSTRUCTION`) and falls back to `default` rather
    than raising if it's missing or malformed -- a model's mistake here
    shouldn't crash the turn.
    """
    lines = answer.strip().splitlines()
    if lines and lines[-1].strip().lower().startswith("next_due_in:"):
        try:
            value = float(lines[-1].split(":", 1)[1].strip())
            return "\n".join(lines[:-1]).strip(), value
        except ValueError:
            pass
    return answer.strip(), default


async def resolve_event(alias: str, replay: TurnReplay) -> tuple[str, float]:
    """Resolve a base-module event: what happens now that `alias` is due,
    and how long until it's next due -- inf (never again, see `pop_event`)
    if the answer omits `next_due_in` entirely, unlike the character
    module's 1-second default. A base event has no standing agenda to
    keep acting on; it's done unless told otherwise.

    Never responder="human": no player is ever behind a base event (there's
    no `character.interaction_type` to branch on, since the character
    module isn't what's driving this popped entity). Between "host" and
    "subagent" -- see `story_simulator.resolve`'s module docstring for what
    "subagent" buys -- `config.event_responder()` decides, defaulting
    to "host" so nothing changes unless a deployment opts in via
    STORY_SIM_RESPONDER.
    """
    request = JudgmentRequest(prompt=f"{alias} is due.\n\n{_NEXT_DUE_IN_INSTRUCTION}")
    answer = await replay.resolve(request, responder=event_responder())
    return _parse_next_due_in(answer, default=float("inf"))


async def process_event(registrar: Registrar, alias: str, replay: TurnReplay, session) -> str:
    """Base module's process event box: Advance clock -> Resolve event ->
    Predict next event -> Push event -- no character-communication step
    first: a base event has no agency to ask "what do you do" of, it just
    resolves.
    """
    _current_world_time[session] = advance_clock(registrar, alias)
    narration, next_due_in = await resolve_event(alias, replay)
    due_at = predict_next_event(registrar, alias, next_due_in)
    push_event(registrar, alias, due_at, time=_next_time_stamp(session))
    return narration


async def _run_event_loop(
    registrar: Registrar,
    session,
    *,
    resume_alias: str | None = None,
    replay: TurnReplay | None = None,
) -> tuple[str | None, TurnReplay | None, str, str | None]:
    """The Event-driven simulation subgraph itself: Pop event -> Valid? ->
    Process event (which itself advances the clock first), looping until
    either a NeedsExternalInput pauses it (returned to the caller, not
    raised further) or the queue empties.

    Always the base path today (`pop_event`/`process_event`, no notion of
    character at all, what this module's own docstring promises works with
    nothing character/npc/spatial layered on top) -- this loop used to
    dispatch through its own `_process_due_entity` seam so a
    character-aware pair (`spatial.pop_event`/`process_event`) could
    branch in depending on `story_simulator.config.enabled_modules`; that
    branch moved out to `shelved/` (see `docs/architecture.md`) pending a
    rewrite, and with it gone there was no longer a second destination for
    the seam to pick between, so it called `process_event` directly
    instead. A future character-aware branch would need to reintroduce its
    own dispatch step rather than assume this one still exists.

    `resume_alias`/`replay` re-enter the loop for a specific turn already
    in progress (what `advance_simulation` is resuming, decoded from its
    `resume_token`) instead of popping fresh -- `replay`'s answers-so-far
    mean everything up to the newest still-unanswered judgment call
    replays from cache (see `story_simulator.resolve.TurnReplay`), and if
    that call now completes, execution falls straight through into the
    ordinary loop below for whatever's next, rather than returning
    immediately. There's a single `process_event` call site, not one per
    branch: `alias` starts as `resume_alias` (possibly None) and the loop
    only pops/validates a fresh one when `alias` is still None, so a
    resumed turn skips straight to processing while a fresh one falls
    through the same two checks first -- deliberately, so `pop_event`/
    `is_event_valid` read as happening *before* `process_event` in this
    function's own source order too, not just at runtime for the common
    case (an entity-reachability trace of this function orders its
    dotted-arrow chain by first occurrence in source, and two separate
    call sites -- the resume branch textually first -- used to make that
    chain read backwards).

    Returns (alias, replay, prompt, responder): `alias`/`replay`/`responder`
    are None only when the queue is empty (nothing left to stash);
    otherwise `alias`/`replay` are exactly what `advance_simulation` needs
    to encode into a `resume_token` for resuming this same pause point, and
    `responder` ("host" or "subagent", never "human" -- see
    `resolve_event`) says who it's asking.
    """
    if resume_alias is not None:
        assert replay is not None

    alias = resume_alias
    while True:
        if alias is None:
            alias = pop_event(registrar)
            if alias is None:
                return None, None, "Nothing scheduled.", None
            if not is_event_valid(registrar, alias):
                alias = None
                continue
            replay = TurnReplay(answers=[])
        try:
            await process_event(registrar, alias, replay, session)
        except NeedsExternalInput as e:
            return alias, replay, e.prompt, e.responder
        # No exception: this turn resolved fully -- reset alias to force a
        # fresh pop next iteration. A base event always pauses
        # (responder="host" or "subagent", per config.event_responder() --
        # never "human", see resolve_event) unless this exact call was
        # already answered by a prior replay.
        alias = None


def _encode_token(alias: str, answers: list[str]) -> str:
    """Serialize a paused turn's resumption state into an opaque token.

    Self-contained, not a lookup key into server memory -- the host
    round-trips this same string back via `advance_simulation`'s own
    `resume_token` argument, so whichever subprocess decodes it (even a
    fresh one after a restart) can resume identically. No `_pending_turns`-
    style session dict needed, matching this module's own
    `stateless_client` mandate (see the `__iacs__` marker at the top).
    """
    payload = json.dumps({"alias": alias, "answers": answers}).encode()
    return base64.urlsafe_b64encode(payload).decode()


def _decode_token(resume_token: str) -> tuple[str, list[str]]:
    payload = json.loads(base64.urlsafe_b64decode(resume_token.encode()))
    return payload["alias"], payload["answers"]


def _resolve_args(resume_token: str | None, answer: str | None) -> tuple[str | None, TurnReplay | None]:
    """Shared resume_token/answer validation + decode for `advance_simulation`."""
    if resume_token is None:
        if answer is not None:
            raise ValueError("answer given without resume_token -- nothing to answer yet.")
        return None, None
    if answer is None:
        raise ValueError("resume_token given without an answer.")
    alias, prior_answers = _decode_token(resume_token)
    return alias, TurnReplay(answers=[*prior_answers, answer])


def _wrap_loop_result(alias: str | None, replay: TurnReplay | None, prompt: str, responder: str | None) -> dict:
    """Shared result shape for `advance_simulation`."""
    if alias is None:
        return {"status": "done", "narration": prompt}
    return {
        "status": "input_required",
        "prompt": prompt,
        "responder": responder,
        "resume_token": _encode_token(alias, replay.answers),
    }


# ---------------------------------------------------------------------------
# Tool implementations -- `mcp_server.py`'s `@server.tool()` functions unpack
# `Context` into `session` (`ctx.request_context.session`) and call these
# directly; the tool docstrings there are the host-facing contract, these
# are the actual behavior.
# ---------------------------------------------------------------------------


def start_world(session, save_dir: str, scenario_dir: str | None = None) -> str:
    """Open a world save for this session, seeding it from `scenario_dir` if it's empty.

    The loose seed *.yaml under scenario_dir is only ever merged into the
    registry the first time this save_dir is opened (a brand-new schema has
    no component types yet) — a resumed save's accumulated state already
    lives in the persisted registry, so reloading the seed YAML again on
    every start_world call would re-merge the same starting entities
    repeatedly.

    Args:
        save_dir: Directory holding (or to hold) this world's save data.
        scenario_dir: Starting scenario to seed a brand-new save_dir from
            (an EC directory, e.g. containing scenario.yaml). Defaults to
            story-simulator's plain default world (a player, a door, an
            empty expanse). Ignored if save_dir already has any save data.
    """
    save_dir_path = Path(save_dir)
    scenario_path = Path(scenario_dir) if scenario_dir else DEFAULT_WORLD_DIR
    save_dir_path.mkdir(parents=True, exist_ok=True)
    _seed_save_dir(save_dir_path, scenario_path)

    _ensure_postgres_running()
    _ensure_postgres_schema(save_dir_path)
    registrar = Registrar.load(registry_url(save_dir_path))
    if not registrar.registry.component_types:
        # WORLD_HISTORY_DIRNAME and WORLD_DIRNAME are both _export_world_yaml's
        # own output, derived from (and redundant with) each other and with
        # the original seed -- WORLD_HISTORY_DIRNAME's content is a strict
        # superset of WORLD_DIRNAME's rows, which are in turn a strict
        # superset of the seed's own content (still present as each entity's
        # earliest historical row). Load exactly one, in that preference
        # order, rather than every *.yaml file under save_dir: concatenating
        # all of them (including both subdirectories at once) would rely on
        # whichever one's rows happened to sort last to win the resulting
        # duplicate top-level keys -- an accident of sort order, not a real
        # guarantee, and not a union either way (YAML's last-key-wins
        # replaces, it doesn't merge). Recursing into the *chosen* directory
        # (rather than requiring one fixed filename) still lets a save's
        # author split it across as many files as they like -- only the
        # top-level choice between "history", "current", or "neither yet
        # exported, fall back to everything under save_dir" needs to be
        # exclusive.
        history_dir = save_dir_path / WORLD_HISTORY_DIRNAME
        world_dir = save_dir_path / WORLD_DIRNAME
        found = (
            (_yaml_files(history_dir) if history_dir.is_dir() else [])
            or (_yaml_files(world_dir) if world_dir.is_dir() else [])
            or _yaml_files(save_dir_path)
        )
        if found:
            # Merged as one WORLD_FILE_ID-keyed string, not passed as
            # input_dirs (which would key each file by its own path instead)
            # -- see WORLD_FILE_ID's comment for why every write must share
            # one source key.
            seed_text = "\n".join(f.read_text() for f in found)
            registrar.update(
                input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: seed_text}
            )

    _registrars[session] = registrar
    _save_dirs[session] = save_dir_path
    return (
        f"World opened at {save_dir_path}. Component types: {registrar.registry.component_types}. "
        "Call view_registry or view_entity to see what's there."
    )


def view_registry(session, component_type: str) -> str:
    """View all recorded data for one component type (e.g. "position", "object", "character").

    Covers both the starting scenario and everything recorded since, since
    it reads straight from the registry.
    """
    registrar = _get_registrar(session)
    return registrar.view_df(component_type).to_csv()


def view_entity(session, entity_id: str) -> str:
    """Return every recorded component instance for a specific entity.

    Args:
        entity_id: Entity hash, alias, or unambiguous path fragment (e.g.
            "player", "desk", or "journaling_desk.desk").
    """
    registrar = _get_registrar(session)
    resolved_id = registrar.get_entity_id(entity_id)
    if resolved_id is None:
        return f"No data found for {entity_id!r}."
    lines = []
    for component_type in sorted(registrar.registry.component_types):
        df = safe_view(registrar, component_type)
        if df is None or df.empty or "entity_id" not in df.columns:
            continue
        matches = df[df["entity_id"] == resolved_id]
        for _, row in matches.iterrows():
            fields = {k: v for k, v in row.items() if k not in ("entity_id", "entity_id.alias")}
            lines.append(f"{component_type}: {fields}")
    if not lines:
        return f"No data found for {entity_id!r}."
    return f"# {entity_id}\n" + "\n".join(lines)


def update_registry(session, yaml_string: str) -> str:
    """Merge entity-first YAML into the world registry, run through the same ETL as save files.

    Args:
        yaml_string: Entity-first YAML content to merge in.
    """
    registrar = _get_registrar(session)
    save_dir = _get_save_dir(session)
    _update_registry_and_sync(registrar, save_dir, yaml_string, session)
    return "Merged into the registry and synced to save_dir/world.yaml."


async def advance_simulation(session, resume_token: str | None = None, answer: str | None = None) -> dict:
    """Fast-forward through any due entities, and pause whenever a turn
    needs input only outside story-simulator's own process can supply.

    The base event-driven simulation (see this module's own docstring) --
    every due entity resolves via responder="host" or "subagent" (see
    `config.event_responder`), no character/NPC concept at all.
    (A character-aware branch used to layer player/NPC turns on top of
    this; moved out to `shelved/` pending a rewrite -- see
    `docs/architecture.md`.)

    Call with neither argument to start (or continue after a prior call
    finished with nothing left scheduled). That, and every later call,
    returns either ``{"status": "done", "narration": ...}`` or
    ``{"status": "input_required", "prompt": ..., "responder": "host" or
    "subagent", "resume_token": ...}``. On the latter, decide what happens
    yourself if `responder` is "host", or follow `prompt`'s own instruction
    to delegate to an isolated subagent if it's "subagent" -- either way,
    call again with that exact `resume_token` and your `answer` -- no
    separate tool, and no server-side state to lose: `resume_token` carries
    everything needed to resume, so it survives an MCP disconnect/reconnect
    between calls too.

    Args:
        resume_token: The `resume_token` from this session's last
            `input_required` result, or omitted to start/continue fresh.
        answer: What happens for the entity that result's `prompt` asked
            about (optionally ending with a `next_due_in: <seconds>` line
            -- omit it if there's nothing further to happen). Omit `answer`
            itself along with `resume_token` on a fresh call.
    """
    registrar = _get_registrar(session)
    resume_alias, replay = _resolve_args(resume_token, answer)
    alias, replay, prompt, responder = await _run_event_loop(
        registrar, session, resume_alias=resume_alias, replay=replay
    )
    return _wrap_loop_result(alias, replay, prompt, responder)
