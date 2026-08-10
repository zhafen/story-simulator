"""MCP server exposing story-simulator's world-state and event-loop tools.

story-simulator is *just* this server — there is no in-process agent loop
here. `advance_simulation` runs ONE event-driven simulation loop (one
function per step -- see `_run_event_loop`), built entirely on
`story_simulator.core`'s base `pop_event`/`predict_event`/`push_event` --
see `core.py`'s own docstring for what that guarantees with nothing
layered on top. The loop fast-forwards through anything it can resolve on
its own, and pauses whenever a turn needs input only the connected host
can supply -- an entity's own resolution -- handing control back to
whatever MCP-aware host is connected (a human's chat agent, an automated
harness, ...). That host decides what happens itself (`responder="host"`,
the default) or is asked to delegate to its own isolated subagent
mechanism instead (`responder="subagent"`, opt in via
STORY_SIM_BASE_RESPONDER -- see `story_simulator.config.base_event_responder`)
-- see `advance_simulation`'s own `responder` field -- then calls
`advance_simulation` again with its decision (recorded via `update_registry`) and
the `resume_token` it was given, to resume the loop -- Multi Round-Trip
Requests (MRTR, MCP spec 2026-07-28), not a second dedicated tool.
`view_registry`/`view_entity`/`update_registry` remain directly callable
too, for anything outside that loop.

Character/NPC/terrain/physics/spatial-perception behavior (`perceive`,
`advance_npc_turn`, `generate_terrain`, `resolve_physics`, and the
character-aware branch this file's `_run_event_loop` used to take) has
been moved out to `shelved/` (see `docs/architecture.md`) pending a
rewrite -- not deleted, and easy to pull back in piece by piece; see git
history for exactly what those looked like at removal.

The judgment resolver behind all of this (`story_simulator.resolve`) is
what lets `resolve_base_event` reach a real decision from any nesting
depth without every intervening function having to be a generator -- see
that module's docstring.

Structurally mirrors `iacs/iacs/mcp_server.py`: a session-scoped `Registrar`
kept in a `weakref.WeakKeyDictionary` (so a session's world state is cleaned
up automatically once the session ends), plain `@server.tool()` functions,
`server.run(transport="stdio")`.
"""

from __future__ import annotations

__iacs__ = {"solution of": "story_simulator_mission.stateless_client"}

import base64
import json
import shutil
import subprocess
import time
import urllib.parse
import weakref
from pathlib import Path

import psycopg
import psycopg.sql
from iacs.registrar import Registrar
from mcp.server.fastmcp import Context, FastMCP

from story_simulator import core
from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    MANIFEST_DIR,
    WORLD_FILE_ID,
    base_event_responder,
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
# _run_event_loop from the popped entity's own `next_due` (see
# core.advance_clock: "the popped entity's own next_due becomes 'now'
# for this turn") and read by _next_time_stamp for every write anything
# does while resolving that entity's turn, so "how recent is this row" and
# "when is X next due" share one clock instead of the wall clock. Session-
# scoped process memory, not persisted -- a subprocess restart mid-turn
# resets it to 0.0 until the next entity pop re-derives it, a known gap
# (see docs/manifest/story-simulator.yaml: world_time_concept) accepted
# for now in favor of not introducing a separate persisted clock entity.
_current_world_time: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# The last stamp _next_time_stamp actually handed out, per session -- lets
# it nudge apart same-world-time writes (see _next_time_stamp) instead of
# handing out the same value repeatedly.
_last_time_stamp: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# Tie-breaking nudge for _next_time_stamp -- a whole 1, not a fraction of a
# second; see that function's docstring for why.
_TIE_EPSILON = 1

# It's how a base-module event tells the loop it's done (see
# resolve_base_event's default=inf) when the next_due_in line is omitted,
# not a mistake to fall back from with a hardcoded interval.
_BASE_NEXT_DUE_IN_INSTRUCTION = (
    "If there's more to happen, end your answer with a line formatted "
    "exactly as `next_due_in: <seconds>` stating how long from now. Omit "
    "that line entirely if this is finished and shouldn't happen again."
)


def _get_registrar(ctx: Context) -> Registrar:
    """Return this session's open world Registrar, or raise a clear error if none is open."""
    session = ctx.request_context.session
    if session not in _registrars:
        raise ValueError("No world open for this session yet — call start_world first.")
    return _registrars[session]


def _get_save_dir(ctx: Context) -> Path:
    return _save_dirs[ctx.request_context.session]


def _next_time_stamp(ctx: Context) -> float:
    """The world-time stamp for `position.time` and friends: this session's
    current in-fiction "now" (seconds since world creation).

    Reads `_current_world_time`, set in `_run_event_loop` from the popped
    entity's own `next_due` (see `core.advance_clock`) -- every write made
    while resolving one entity's turn shares that same "now", the same
    world-time axis `next_due.value` itself uses, rather than a wall-clock
    substitute. Falls back to 0.0 if nothing has been popped yet for this
    session (e.g. a stray `update_registry` call before `advance_simulation`
    is ever run).

    Two writes at the same world time -- several update_registry calls
    resolving one turn, or any number of stray calls before the first event
    is ever popped -- would otherwise tie, and Registry.view_current's tie
    handling is presently arbitrary (iacs's own _seq write-order column,
    zhafen/iacs#94, isn't merged into this submodule pointer yet). Nudged
    apart here instead by _TIE_EPSILON, so a later write always gets a
    strictly higher stamp than an earlier one at the same world time and
    "most recent write wins" still holds -- a per-project stopgap to drop
    once #94 merges and iacs's own tie-break can be relied on instead.

    _TIE_EPSILON is a whole 1, not a fraction of a second, for two reasons
    observed directly: `math.nextafter`'s smallest-possible step starting
    from 0.0 lands in subnormal-float range, which the registry's
    duckdb/ibis pipeline was seen flushing back to 0.0 -- silently re-tying
    the very rows this is meant to keep apart; and this same stamp also
    backfills `description.time`, an iacs builtin declared `type: int` (not
    story-simulator's to change), which truncates any fractional nudge to
    nothing for the same reason. A whole-integer nudge survives both.
    """
    session = ctx.request_context.session
    world_time = _current_world_time.get(session, 0.0)
    last = _last_time_stamp.get(session)
    stamp = world_time if last is None or world_time > last else last + _TIE_EPSILON
    _last_time_stamp[session] = stamp
    return stamp


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

    The one Postgres-specific piece of this file -- everywhere else talks to
    the registry database only through `config.registry_url`/`Registrar`,
    which stay backend-agnostic via `ibis.connect`. `CREATE SCHEMA` is a
    one-off admin statement against the database, not registry data, so it's
    a plain psycopg connection rather than something routed through
    `Registrar`/`ibis`. Has to run before `Registrar.load` ever connects
    with that schema name: an unknown schema in a connection's search_path
    fails silently rather than erroring (see `config.registry_url`).
    """
    schema = registry_schema_name(save_dir)
    with psycopg.connect(resolve_database_dsn(), autocommit=True) as con:
        con.execute(
            psycopg.sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                psycopg.sql.Identifier(schema)
            )
        )


server = FastMCP(
    "story-simulator",
    instructions=(
        "You are the game master for a story-simulator world: a text simulation whose "
        "state lives in a structured entity/component registry, not just your own context, "
        "run as an event-driven simulation (one entity due at a time, scheduled by its "
        "own next_due) rather than a fixed per-turn loop.\n\n"
        "Call start_world once, at the beginning, to open or seed a save. Then call "
        "advance_simulation with no arguments: it pauses on every due entity in turn, "
        "returning {\"status\": \"input_required\", \"prompt\": ..., \"responder\": \"host\" or "
        "\"subagent\", \"resume_token\": ...}. If responder is \"host\", decide what happens "
        "yourself, from your own context. If it's \"subagent\", the prompt itself asks you to "
        "delegate to your own isolated subagent mechanism (e.g. an Agent/Task tool) instead of "
        "answering inline -- follow that instruction rather than answering directly. Either "
        "way, call advance_simulation again with that exact resume_token and the answer to "
        "resume the loop. State the outcome and end your answer with a line formatted exactly "
        "as `next_due_in: <seconds>` if this entity has more to do, or omit that line if it's "
        "finished. It will keep asking (a new resume_token each time -- always use the one "
        "from the latest result) until either it needs you once more or the schedule empties "
        "(\"status\": \"done\").\n\n"
        "Record what happened yourself via update_registry (new positions, new entities, "
        "changed details — reusing existing aliases; attach new data to an existing entity "
        "via a `same_as` component rather than creating a disconnected duplicate). "
        "`description` and `state` are both current-value components: a new write becomes "
        "the entity's current one, both for view_entity and for the save's exported YAML "
        "(older writes stay recorded as history — view_entity still shows all of them). "
        "Write the whole updated description each time, not a diff, and use `state` for a "
        "short current status word or phrase (e.g. a door being \"open\") rather than folding "
        "it into the description text.\n\n"
        "Use view_registry/view_entity to look up what's already known before deciding — "
        "don't invent entities or details nothing has established."
    ),
)


@server.tool()
def start_world(save_dir: str, ctx: Context, scenario_dir: str | None = None) -> str:
    """Open a world save for this session, seeding it from `scenario_dir` if it's empty.

    The loose seed *.yaml under save_dir is only ever merged into the
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
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.start_world"}
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

    _registrars[ctx.request_context.session] = registrar
    _save_dirs[ctx.request_context.session] = save_dir_path
    return (
        f"World opened at {save_dir_path}. Component types: {registrar.registry.component_types}. "
        "Call view_registry or view_entity to see what's there."
    )


@server.tool()
def view_registry(component_type: str, ctx: Context) -> str:
    """View all recorded data for one component type (e.g. "position", "object", "character").

    Covers both the starting scenario and everything recorded since, since
    it reads straight from the registry.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.view_registry"}
    registrar = _get_registrar(ctx)
    return registrar.view_df(component_type).to_csv()


@server.tool()
def view_entity(entity_id: str, ctx: Context) -> str:
    """Return every recorded component instance for a specific entity.

    Args:
        entity_id: Entity hash, alias, or unambiguous path fragment (e.g.
            "player", "desk", or "journaling_desk.desk").
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.view_entity"}
    registrar = _get_registrar(ctx)
    resolved_id = registrar.get_entity_id(entity_id)
    if resolved_id is None:
        return f"No data found for {entity_id!r}."
    lines = []
    for component_type in sorted(registrar.registry.component_types):
        df = core.safe_view(registrar, component_type)
        if df is None or df.empty or "entity_id" not in df.columns:
            continue
        matches = df[df["entity_id"] == resolved_id]
        for _, row in matches.iterrows():
            fields = {k: v for k, v in row.items() if k not in ("entity_id", "entity_id.alias")}
            lines.append(f"{component_type}: {fields}")
    if not lines:
        return f"No data found for {entity_id!r}."
    return f"# {entity_id}\n" + "\n".join(lines)


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

    Each is a directory, not a single fixed filename, because
    `export_manifest` writes one EC file per original source filepath --
    today that's always exactly one file (every registrar.update() call
    across this project shares `WORLD_FILE_ID` as its source key), but the
    directory is what leaves room for a save to be split across more files
    later without a format change, matching iacs's own principle of letting
    an EC source be organized across as many files as its author wants.
    `start_world`'s loader recurses into whichever directory it picks rather
    than assuming one file lives there.

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


def _update_registry_and_sync(registrar: Registrar, save_dir: Path, yaml_string: str, ctx: Context) -> None:
    """Merge `yaml_string` into the registry, then sync `save_dir`'s YAML to match."""
    registrar.update(
        input_dirs=[str(MANIFEST_DIR)],
        yaml_strings={WORLD_FILE_ID: yaml_string},
        time=_next_time_stamp(ctx),
    )
    _export_world_yaml(registrar, save_dir)


@server.tool()
def update_registry(yaml_string: str, ctx: Context) -> str:
    """Merge entity-first YAML into the world registry, run through the same ETL as save files.

    Args:
        yaml_string: Entity-first YAML content to merge in.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.update_registry"}
    registrar = _get_registrar(ctx)
    save_dir = _get_save_dir(ctx)
    _update_registry_and_sync(registrar, save_dir, yaml_string, ctx)
    return "Merged into the registry and synced to save_dir/world.yaml."


def _parse_next_due_in(answer: str, default: float = 1.0) -> tuple[str, float]:
    """Split a resolve_base_event answer into (narration, next_due_in).

    Looks for a trailing `next_due_in: <seconds>` line (see
    `_BASE_NEXT_DUE_IN_INSTRUCTION`) and falls back to `default` rather
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


async def resolve_base_event(alias: str, replay: TurnReplay) -> tuple[str, float]:
    """Resolve a base-module event: what happens now that `alias` is due,
    and how long until it's next due -- inf (never again, see
    `core.pop_event`) if the answer omits `next_due_in` entirely, unlike
    the character module's 1-second default. A base event has no standing
    agenda to keep acting on; it's done unless told otherwise.

    Never responder="human": no player is ever behind a base event (there's
    no `character.interaction_type` to branch on, since the character
    module isn't what's driving this popped entity). Between "host" and
    "subagent" -- see `story_simulator.resolve`'s module docstring for what
    "subagent" buys -- `config.base_event_responder()` decides, defaulting
    to "host" so nothing changes unless a deployment opts in via
    STORY_SIM_BASE_RESPONDER.
    """
    request = JudgmentRequest(prompt=f"{alias} is due.\n\n{_BASE_NEXT_DUE_IN_INSTRUCTION}")
    answer = await replay.resolve(request, responder=base_event_responder())
    return _parse_next_due_in(answer, default=float("inf"))


async def process_base_event(registrar: Registrar, alias: str, replay: TurnReplay, ctx: Context) -> str:
    """Base module's process event box: Resolve event -> Predict event ->
    Push event -- no character-communication step first: a base event has
    no agency to ask "what do you do" of, it just resolves.
    """
    narration, next_due_in = await resolve_base_event(alias, replay)
    due_at = core.predict_event(registrar, alias, next_due_in)
    core.push_event(registrar, alias, due_at, time=_next_time_stamp(ctx))
    return narration


async def _run_event_loop(
    registrar: Registrar,
    save_dir: Path,
    ctx: Context,
    *,
    resume_alias: str | None = None,
    replay: TurnReplay | None = None,
) -> tuple[str | None, TurnReplay | None, str, str | None]:
    """The Event-driven simulation subgraph itself: Pop event -> Valid? -> Advance
    clock -> Process event, looping until either a NeedsExternalInput pauses it
    (returned to the caller, not raised further) or the queue empties.

    Always the base path today (`core.pop_event`/`process_base_event`, no
    notion of character at all, what `core.py`'s own docstring promises
    works with nothing layered on top) -- `_process_due_entity` used to
    also branch to a character-aware pair (`spatial.pop_event`/
    `process_event`) depending on `story_simulator.config.enabled_modules`,
    moved out to `shelved/` (see `docs/architecture.md`) pending a rewrite.
    `_process_due_entity` is kept as its own step (rather than inlined
    here) specifically as the seam that branching returns to.

    `resume_alias`/`replay` re-enter the loop for a specific turn already
    in progress (what `advance_simulation` is resuming, decoded from its
    `resume_token`) instead of popping fresh -- `replay`'s answers-so-far
    mean everything up to the newest still-unanswered judgment call
    replays from cache (see `story_simulator.resolve.TurnReplay`), and if
    that call now completes, execution falls straight through into the
    ordinary loop below for whatever's next, rather than returning
    immediately.

    Returns (alias, replay, prompt, responder): `alias`/`replay`/`responder`
    are None only when the queue is empty (nothing left to stash);
    otherwise `alias`/`replay` are exactly what `advance_simulation` needs
    to encode into a `resume_token` for resuming this same pause point, and
    `responder` ("host" or "subagent", never "human" -- see
    `resolve_base_event`) says who it's asking.
    """
    if resume_alias is not None:
        assert replay is not None
        try:
            await _process_due_entity(registrar, save_dir, resume_alias, replay, ctx)
        except NeedsExternalInput as e:
            return resume_alias, replay, e.prompt, e.responder
        # No exception: this turn finished. Fall through to the ordinary
        # loop below rather than returning, since more entities may now be due.

    while True:
        alias = core.pop_event(registrar)
        if alias is None:
            return None, None, "Nothing scheduled.", None
        if not core.is_event_valid(registrar, alias):
            continue
        _current_world_time[ctx.request_context.session] = core.advance_clock(registrar, alias)
        replay = TurnReplay(answers=[])
        try:
            await _process_due_entity(registrar, save_dir, alias, replay, ctx)
        except NeedsExternalInput as e:
            return alias, replay, e.prompt, e.responder
        # No exception: this turn resolved fully -- loop back and pop
        # whatever's due next. A base event always pauses (responder="host"
        # or "subagent", per config.base_event_responder() -- never
        # "human", see resolve_base_event) unless this exact call was
        # already answered by a prior replay.


async def _process_due_entity(
    registrar: Registrar,
    save_dir: Path,
    alias: str,
    replay: TurnReplay,
    ctx: Context,
) -> str:
    """Dispatch one popped entity's turn to the base module's own process-event box.

    A top-level function rather than a closure nested inside
    `_run_event_loop` precisely so it becomes its own entity once iacs
    parses this file -- a nested, undocumented closure made
    `_run_event_loop`'s real dispatch invisible to iacs's parsed call graph
    (see `docs/architecture/advance_simulation.md`). Kept as its own
    single-branch step even now that there's only one module to dispatch
    to, since it's the seam a character-aware branch returns to.
    """
    return await process_base_event(registrar, alias, replay, ctx)


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


@server.tool()
async def advance_simulation(ctx: Context, resume_token: str | None = None, answer: str | None = None) -> dict:
    """Fast-forward through any due entities, and pause whenever a turn
    needs input only outside story-simulator's own process can supply.

    The base event-driven simulation (see `core.py`) -- every due entity
    resolves via responder="host" or "subagent" (see
    `config.base_event_responder`), no character/NPC concept at all.
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
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.advance_simulation"}
    registrar = _get_registrar(ctx)
    save_dir = _get_save_dir(ctx)
    resume_alias, replay = _resolve_args(resume_token, answer)
    alias, replay, prompt, responder = await _run_event_loop(
        registrar, save_dir, ctx, resume_alias=resume_alias, replay=replay
    )
    return _wrap_loop_result(alias, replay, prompt, responder)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
