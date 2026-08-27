"""The event-driven simulation kernel: everything that makes
story-simulator's MCP tools possible, session state included.

`mcp_server.py` only wires this up to the MCP protocol (`@server.tool()`
functions that unpack `Context` into a plain session id and call
straight into here).

Not framework-agnostic: responders (`story_simulator.config.event_responder`,
`story_simulator.resolve`) are central to how this project works, not an
optional layer on top of it -- so this module carries the bulk of
`mcp_server.py`'s own implementation rather than staying a small
Context-free base. Splitting pieces back out (e.g. if a second host
protocol besides MCP ever needs this logic) is still open to do later,
as needed.
"""

from __future__ import annotations

__iacs__ = {
    "solution of": "story_simulator_mission.stateless_client",
}

import base64
import json
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

import pandas as pd
import psycopg
import psycopg.sql
from emc2p.mcp_server import SOURCE_KEY, RegistrarSessions
from emc2p.registrar import Registrar

from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    MANIFEST_DIR,
    event_responder,
    keyed_subagent_time_budget_seconds,
    registry_schema_name,
    registry_url,
    resolve_database_dsn,
)
from story_simulator.resolve import JudgmentRequest, NeedsExternalInput, TurnReplay

# save_dir's two export subdirectories, each holding one EC yaml file per
# original source -- directories, not fixed filenames, so a save can be split.
WORLD_DIRNAME = "world"
WORLD_HISTORY_DIRNAME = "world_history"

# The single well-known entity `process_event` writes each popped event's
# end_time onto, as a `world_clock` component -- see `_next_time_stamp`.
WORLD_CLOCK_ALIAS = "simulation_clock"


def safe_view(
    registrar: Registrar, fields: str | list[str], aliases: str | list[str] | None = None
) -> pd.DataFrame | None:
    """Execute `registrar.view(fields, aliases)`, or None if that component type isn't loaded yet."""
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view(fields, aliases).execute()
    except KeyError:
        return None


def safe_view_current(
    registrar: Registrar, fields: str | list[str], aliases: str | list[str] | None = None
) -> pd.DataFrame | None:
    """Like `safe_view`, but resolves each field's current row per entity.

    Uses `registrar.view_current`.  A component type with no `time_dimension` field
    behaves exactly like `safe_view` (every row is "current").
    """
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view_current(fields, aliases).execute()
    except KeyError:
        return None


# Event-driven simulation loop -- one function per box in the turn-anatomy
# diagram (see docs/architecture.md).

_TERMINAL_EVENT_STATES = ("complete", "interrupted")


def pop_event(registrar: Registrar) -> str | None:
    """Pop event box: whichever `event` entity's end_time comes soonest, or
    None if nothing is currently scheduled.

    An event only enters consideration once it has both start_time and
    duration set -- one not yet scheduled (event_state "not started", or
    no event_state row at all yet) isn't a candidate. A terminal event
    (event_state "complete" or "interrupted") is filtered out too. end_time is
    start_time + duration, computed fresh from the registry every call --
    there's no separate reschedule write to keep in sync with it, since an
    event's own timing isn't revised once set (see this section's own
    docstring).

    A plain read, not a destructive dequeue -- `story_simulator.resolve`'s
    replay-from-the-top mechanism depends on calling this again and again
    being safe.
    """
    if "event" not in registrar.registry.component_types:
        return None
    events = registrar.view_current(["event.start_time", "event.duration"]).execute()
    events = events.dropna(subset=["event.start_time", "event.duration"])
    if events.empty:
        return None
    states = safe_view_current(registrar, "event_state.value")
    if states is not None:
        terminal_ids = set(states[states["event_state.value"].isin(_TERMINAL_EVENT_STATES)]["entity_id"])
        events = events[~events["entity_id"].isin(terminal_ids)]
    if events.empty:
        return None
    end_time = events["event.start_time"] + events["event.duration"]
    return events.assign(_end_time=end_time).sort_values("_end_time").iloc[0]["entity_id.alias"]


def is_event_valid(registrar: Registrar, alias: str) -> bool:
    """Valid? box: is `alias` still a real, eligible entity.

    Always true today by construction -- `pop_event` re-reads current
    state fresh rather than pre-computing events into a queue, so the
    staleness problem this check exists for doesn't arise yet. Seam for a
    future lookahead/precomputed-event design to extend.
    """
    return registrar.get_entity_id(alias) is not None


def advance_clock(registrar: Registrar, alias: str) -> float:
    """Advance clock box: the popped event's own start_time + duration
    becomes "now" for this turn.

    Its end_time, the moment it actually resolves, not when it started.
    Only computes the value -- `process_event` is what actually persists
    it as world time's new current value (see `WORLD_CLOCK_ALIAS`/
    `_next_time_stamp`); the popped event's own timing is still the only
    source that value ever comes from.
    """
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return 0.0
    events = registrar.view_current(["event.start_time", "event.duration"]).execute()
    match = events[events["entity_id"] == entity_id]
    if match.empty:
        return 0.0
    row = match.iloc[0]
    return float(row["event.start_time"]) + float(row["event.duration"])


def _next_time_stamp(registrar: Registrar) -> float:
    """The world-time stamp for `position.time` and friends: the world's
    current in-fiction "now" (seconds since world creation).

    Reads `world_clock.value` (manifest/builtins.yaml), written in
    `process_event` from the popped event's own start_time + duration (see
    `advance_clock`) onto `WORLD_CLOCK_ALIAS` -- every write made while
    resolving one event's turn shares that same "now", the same
    world-time axis `event.start_time`/`event_state.time`/`outcome` writes
    all use, rather than a wall-clock substitute. A registry entity, not
    process memory scoped to one MCP session -- it survives a session
    reconnect the same way every other piece of world state already does.

    `world_clock` isn't itself flagged `time_dimension` (unlike
    `position.time`/`state.time`/...): a row's own `value` IS the world
    time, so there's no independent "when was this recorded" axis to
    backfill it against -- `Registry.view_current`'s time-dimension
    resolution has nothing to resolve against here. Takes the highest
    recorded value across every accumulated row instead, relying on world
    time only ever moving forward (each event pop's own end_time is at
    least as late as every previously resolved one) rather than on write
    order. Falls back to 0.0 if nothing has been popped yet (e.g. a stray
    `update_registry` call before `advance_simulation` is ever run).
    """
    df = safe_view(registrar, "world_clock.value")
    if df is None or df.empty:
        return 0.0
    return float(df["world_clock.value"].max())


# Session state (which Registrar/save_dir a session is talking to) plus
# view_registry/view_entity/update_registry/consolidate_review themselves.
registrar_sessions = RegistrarSessions(
    time_provider=_next_time_stamp,
    export_dirname=WORLD_DIRNAME,
    export_history_dirname=WORLD_HISTORY_DIRNAME,
    open_tool_name="start_world",
)


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


# Postgres dev-convenience bootstrap -- the one Postgres-specific corner of
# this module; everything else stays backend-agnostic via `ibis.connect`.


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


# Turn resolution


async def resolve_event(alias: str, replay: TurnReplay, end_time: float, session) -> str:
    """Resolve box: ask a responder to interpret `alias` now that its
    end_time has been reached, and hand back whatever it says, for narration.

    The responder is expected to record everything itself via
    update_registry -- this event's own `outcome`, this event's own
    `event_state` transition (complete or interrupted), and whatever it
    changes about the entities it involves (see involved_entity) -- the
    same direct tool-calling pattern it already uses for every other
    write. The prompt spells out that last part explicitly (write changes
    onto the affected entity itself, not just described in this event's
    own outcome text): a weak model otherwise narrates an involved
    entity's new state inside the event's outcome without a separate
    update_registry write for that entity, leaving nothing for a caller
    reading that entity directly to find. This function's only job is to
    ask and hand back the answer; persisting is entirely the responder's
    own, not a return value this code applies on its behalf (see
    `plan_events`, and `process_event`'s own docstring for why there's no
    separate mechanical "update" step).

    Doesn't name a specific component type (e.g. `location`) as an
    example, even though that's what most scenarios so far have needed:
    this prompt is generic across every scenario, and not every event's
    consequence is a location change, so hardcoding one component here
    would bias every scenario toward it. Points at `view_entity` on the
    component type's own name instead (its field descriptions carry
    scenario-specific examples, e.g. `location`'s own doubles as the
    phrasing convention): a model resolving its first-ever write to an
    unfamiliar component type otherwise doesn't think to look up that
    component type's own schema, and improvises a reasonable-but-inconsistent
    phrasing instead.

    `end_time` (the same value `process_event` just fed to `advance_clock`
    -- `alias`'s own start_time + duration, plain arithmetic, not left for
    the responder to infer) is stated explicitly in the prompt: a weak
    model otherwise sometimes reads a due-style ("X is due") framing
    against start_time alone (i.e. when the trip *starts*) rather than
    start_time + duration (when it actually *arrives*), misjudging which
    other events have already resolved by that point -- part of why this
    uses "end_time" rather than "due" throughout, not just here.

    The prompt also states outright that nothing with an earlier end_time
    is still unresolved -- `pop_event`'s own sort guarantees this is the
    earliest-end_time event still pending, so nothing else has resolved
    yet either. Without this stated explicitly, a weak model sometimes
    assumes a *different*, not-yet-resolved entity's event has already
    happened -- reasoning from that other event's start_time or its row's
    position in a table instead of checking its actual `event_state` --
    and writes a wrong outcome for `alias` on top of that wrong
    assumption (e.g. deciding a shared resource a different car "already
    took" is unavailable, when that other car's own trip hasn't resolved
    at all). Deliberately points at checking `event_state` itself
    (already the one place this loop records whether an event is done)
    rather than adding a second, redundant field elsewhere for the same
    fact.

    Never responder="human": no player is ever behind an event here
    (there's no `character.interaction_type` to branch on, since the
    character module isn't what's driving this popped entity). Between
    "host" and "subagent" -- see `story_simulator.resolve`'s module
    docstring for what "subagent" buys -- `config.event_responder()`
    decides, defaulting to "host" so nothing changes unless a deployment
    opts in via STORY_SIM_RESPONDER.
    """
    request = JudgmentRequest(
        prompt=(
            f"{alias}'s end_time (world time {end_time:g}) has been "
            f"reached. Nothing else with an earlier end_time is still "
            f"unresolved -- if another entity's own event hasn't reached "
            f"event_state: complete yet (check via view_entity/"
            f"view_registry, not assumed from its start_time or where it "
            f"appears in a table), treat it as not having happened yet. "
            f"Look up whatever you need (view_entity/"
            f"view_registry, including its involved_entity links) to "
            f"work out what happens, then record it: {alias}'s own "
            f"outcome, {alias}'s own event_state "
            f"(complete if this fully resolves it, interrupted if "
            f"something cuts it short), and anything it changes about the "
            f"entities it involves -- write those changes directly onto "
            f"each affected entity itself, using whichever component type "
            f"actually fits (view_entity on the component type's own name, "
            f"e.g. view_entity('location'), shows its field descriptions "
            f"if you're unsure which one or how to phrase it), not only "
            f"described in {alias}'s own outcome text -- all via "
            f"update_registry."
        )
    )
    return await replay.resolve(request, responder=event_responder(), session=session)


async def plan_events(alias: str, replay: TurnReplay, session) -> str:
    """Plan box: ask a responder whether anything new needs to be
    scheduled as a result of `alias` resolving, creating new `event` entities if so.

    Always asked, even when nothing ends up being scheduled -- "nothing
    follows from this" is this step's own answer to reach, not a case the
    loop skips based on `alias`'s outcome alone (see `process_event`).
    """
    request = JudgmentRequest(
        prompt=(
            f"Given how {alias} just resolved, does anything new need to "
            f"happen as a result? If so, create it now: one or more new "
            f"event entities (their own start_time/duration/event_state/"
            f"involved_entity) via update_registry. If nothing follows "
            f"from this, just say so -- no new events needed."
        )
    )
    return await replay.resolve(request, responder=event_responder(), session=session)


async def process_event(registrar: Registrar, alias: str, replay: TurnReplay, session) -> tuple[str, str]:
    """Process event box: Advance clock -> Resolve event -> Plan events.

    Advance clock is the one exception to "resolve_event/plan_events
    persist everything themselves": `end_time` itself is written here,
    directly, as this world's new `world_clock` value (see
    `WORLD_CLOCK_ALIAS`/`_next_time_stamp`) -- there's no responder
    involved in computing it, so there's no judgment call for a responder
    to persist it through. Otherwise no update-data step: `resolve_event`
    and `plan_events` both write everything else they decide directly via
    update_registry (including `alias`'s own event_state transition), so
    there's nothing left for this function to persist mechanically
    afterward -- unlike the next_due_in mechanism this replaces, which
    needed a code-driven predict/push reschedule step because a plain
    float answer had nothing else able to act on it.
    """
    end_time = advance_clock(registrar, alias)
    registrar.update(
        yaml_strings={SOURCE_KEY: f"{WORLD_CLOCK_ALIAS}:\n    - world_clock:\n        value: {end_time}\n"},
    )
    resolve_narration = await resolve_event(alias, replay, end_time, session)
    plan_narration = await plan_events(alias, replay, session)
    return resolve_narration, plan_narration


async def _run_event_loop(
    registrar: Registrar,
    session,
    *,
    resume_alias: str | None = None,
    replay: TurnReplay | None = None,
) -> tuple[str | None, TurnReplay | None, str, str | None]:
    """The Event-driven simulation subgraph itself: Pop event -> Valid? ->
    Process event, looping until it pauses or the queue empties.

    Process event itself advances the clock first, then asks two
    separate responder calls -- resolve, then plan. Loops until either a
    NeedsExternalInput pauses it (returned to the caller, not raised
    further) or the queue empties.

    One `process_event` call is one full event's worth of work, but not
    necessarily one pause: resolve's own judgment call and plan's own
    judgment call are two separate entries in the same `TurnReplay`
    (see that class's own docstring -- "a single turn can hit more than
    one judgment call before it's done"), so a fresh event typically
    pauses twice in a row (once to resolve, once to plan) before this
    loop ever reaches the bottom and pops the next one -- both under the
    same `resume_token` until the second answer lands, at which point
    `process_event` returns normally and the loop moves on.

    `resume_alias`/`replay` re-enter the loop for a specific turn already
    in progress (what `advance_simulation` is resuming, decoded from its
    `resume_token`) instead of popping fresh -- `replay`'s answers-so-far
    mean everything up to the newest still-unanswered judgment call
    replays from cache, and if that call now completes, execution falls
    straight through into the ordinary loop below for whatever's next,
    rather than returning immediately. There's a single `process_event`
    call site, not one per branch: `alias` starts as `resume_alias`
    (possibly None) and the loop only pops/validates a fresh one when
    `alias` is still None, so a resumed turn skips straight to processing
    while a fresh one falls through the same two checks first --
    deliberately, so `pop_event`/`is_event_valid` read as happening
    *before* `process_event` in this function's own source order too, not
    just at runtime for the common case.

    Returns (alias, replay, prompt, responder): `alias`/`replay`/`responder`
    are None only when the queue is empty (nothing left to stash);
    otherwise `alias`/`replay` are exactly what `advance_simulation` needs
    to encode into a `resume_token` for resuming this same pause point, and
    `responder` ("host" or "subagent", never "human" -- see
    `resolve_event`) says who it's asking.
    """
    if resume_alias is not None:
        assert replay is not None

    # Computed once per call (fresh or resumed), not per event/TurnReplay --
    # applies to the whole advance_simulation invocation, not any one event.
    deadline = time.monotonic() + keyed_subagent_time_budget_seconds()
    if replay is not None:
        replay.deadline = deadline

    alias = resume_alias
    while True:
        if alias is None:
            alias = pop_event(registrar)
            if alias is None:
                return None, None, "Nothing scheduled.", None
            if not is_event_valid(registrar, alias):
                alias = None
                continue
            replay = TurnReplay(answers=[], deadline=deadline)
        try:
            await process_event(registrar, alias, replay, session)
        except NeedsExternalInput as e:
            return alias, replay, e.prompt, e.responder
        # No exception: both resolve and plan answered fully -- reset alias
        # to force a fresh pop next iteration.
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


# Tool implementations -- `mcp_server.py`'s `@server.tool()` functions unpack
# `Context` into `session` and call these directly.


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
        # own output; load exactly one, in that preference order (fullest first).
        history_dir = save_dir_path / WORLD_HISTORY_DIRNAME
        world_dir = save_dir_path / WORLD_DIRNAME
        found = (
            (_yaml_files(history_dir) if history_dir.is_dir() else [])
            or (_yaml_files(world_dir) if world_dir.is_dir() else [])
            or _yaml_files(save_dir_path)
        )
        if found:
            # Merged as one SOURCE_KEY-keyed string, not passed as input_dirs
            # -- see SOURCE_KEY's comment for why every write shares one key.
            seed_text = "\n".join(f.read_text() for f in found)
            registrar.update(
                input_dirs=[str(MANIFEST_DIR)], yaml_strings={SOURCE_KEY: seed_text}
            )

    # Declares the manifest's own component-type schemas (location, event,
    # ...) regardless of whether this save was fresh, resumed, or already declared.
    registrar.update(input_dirs=[str(MANIFEST_DIR)])

    registrar_sessions.set_registrar(session, registrar, export_dir=save_dir_path)
    return (
        f"World opened at {save_dir_path}. Component types: {registrar.registry.component_types}. "
        "Call view_registry or view_entity to see what's there."
    )


async def advance_simulation(session, resume_token: str | None = None, answer: str | None = None) -> dict:
    """Fast-forward through any events whose end_time has been reached,
    and pause when a turn needs input story-simulator's own process can't supply.

    The event-driven simulation (see this module's own docstring): world
    state is `event` entities, each ready to resolve once world time
    reaches its own end_time -- start_time + duration
    (manifest/builtins.yaml's event_components) -- not the acting
    entities (a car, a door, ...) themselves, which carry no schedule of
    their own. Every such event goes through two separate
    responder calls in turn -- resolve (what happened) and plan (what, if
    anything, follows from that) -- each via responder="host" or
    "subagent" (see `config.event_responder`); a fresh event typically
    means two pauses in a row, one per call, before the loop reaches the
    next one. No character/NPC concept at all -- that behavior is
    currently shelved (see `docs/architecture.md`), pending a rewrite.

    Call with neither argument to start (or continue after a prior call
    finished with nothing left scheduled). That, and every later call,
    returns either ``{"status": "done", "narration": ...}`` or
    ``{"status": "input_required", "prompt": ..., "responder": "host" or
    "subagent", "resume_token": ...}``. On the latter, decide what happens
    yourself if `responder` is "host", or follow `prompt`'s own instruction
    to delegate to an isolated subagent if it's "subagent" -- either way,
    record whatever you decide yourself via update_registry (there's no
    structured return value this tool applies on your behalf), then call
    again with that exact `resume_token` and your `answer` -- no separate
    tool, and no server-side state to lose: `resume_token` carries
    everything needed to resume, so it survives an MCP disconnect/reconnect
    between calls too.

    Args:
        resume_token: The `resume_token` from this session's last
            `input_required` result, or omitted to start/continue fresh.
        answer: Your answer to that result's `prompt` -- what an event's
            resolution was, or what (if anything) it schedules next,
            recorded via update_registry before you answer. Omit `answer`
            itself along with `resume_token` on a fresh call.
    """
    registrar = registrar_sessions.get_registrar(session)
    resume_alias, replay = _resolve_args(resume_token, answer)
    alias, replay, prompt, responder = await _run_event_loop(
        registrar, session, resume_alias=resume_alias, replay=replay
    )
    return _wrap_loop_result(alias, replay, prompt, responder)
