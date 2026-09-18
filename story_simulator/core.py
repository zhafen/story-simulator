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

import json
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

import psycopg
import psycopg.sql
import yaml
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
from story_simulator import character
from story_simulator.resolve import JudgmentRequest, NeedsExternalInput, TurnReplay

# save_dir's two export subdirectories, each holding one EC yaml file per
# original source -- directories, not fixed filenames, so a save can be split.
WORLD_DIRNAME = "world"
WORLD_HISTORY_DIRNAME = "world_history"

# The single well-known entity `process_event` writes each popped event's
# end_time onto, as a `world_clock` component -- see `_next_time_stamp`.
WORLD_CLOCK_ALIAS = "simulation_clock"


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
    events = registrar.view_current(["event.start_time", "event.duration"]).to_pandas()
    events = events.dropna(subset=["event.start_time", "event.duration"])
    if events.empty:
        return None
    states = registrar.safe_view_current("event_state.value").to_pandas()
    if not states.empty:
        terminal_ids = set(states[states["event_state.value"].isin(_TERMINAL_EVENT_STATES)]["entity_id"])
        events = events[~events["entity_id"].isin(terminal_ids)]
    if events.empty:
        return None
    end_time = events["event.start_time"] + events["event.duration"]
    return events.assign(_end_time=end_time).sort_values("_end_time").iloc[0]["entity_id.alias"]


def _no_event_ever_recorded(registrar: Registrar) -> bool:
    """True if no `event` entity has ever been written to this world at
    all -- not merely that none are currently eligible (see `pop_event`).

    Distinguishes a world that's actually run its schedule to completion
    (every event reached a terminal state) from one that likely never had
    a schedule in the first place -- e.g. a scenario/manifest that forgot
    to write any `event` entity -- which `pop_event` alone can't tell
    apart: both return None. Unlike `pop_event`, this doesn't filter on
    start_time/duration/event_state at all -- even a half-written event
    entity (missing one of those) still counts as "something was recorded".
    """
    if "event" not in registrar.registry.component_types:
        return True
    return registrar.view_current(["event.start_time"]).to_pandas().empty


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
    events = registrar.view_current(["event.start_time", "event.duration"]).to_pandas()
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
    df = registrar.safe_view("world_clock.value").to_pandas()
    if df.empty:
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


async def resolve_event(
    alias: str,
    replay: TurnReplay,
    end_time: float,
    session,
    decision: str | None = None,
    human_character_alias: str | None = None,
) -> str:
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

    Never responder="human": no player is ever directly asked *through
    the MCP protocol* here -- `process_event` still resolves every event
    (including a character's own turn) through this same call,
    `event_responder()` deciding "host" vs "subagent" the same way
    regardless of whether a character is involved (see resolve.py's own
    docstring for why "host" doesn't actually mean something different
    from "human" mechanically -- both round-trip to the same connected
    agent; "host" already usually *is* an agent relaying to/from a real
    player over ordinary conversation, just not through this protocol's
    own MRTR pause). A character-flagged event's own `decision` (see
    `decide_event`) or `human_character_alias` is threaded in as
    additional context when there is one, rather than resolve_event
    branching on `character.interaction_type` itself -- keeping this
    function's own responder choice independent of whether an NPC's
    decide step ran first.

    `decision`, when given, is an NPC's own already-decided action (see
    `decide_event`/`process_event`) -- resolve_event's job then narrows
    from "what happens" to "record the consequences of what's already
    decided," not re-decide it.

    `human_character_alias`, when given, is a human-voiced character
    involved in this event (see `process_event`'s own branch) -- unlike
    an NPC, there's no separate decide step for one (their action is
    normally already known to the host from the ongoing conversation),
    but nothing here guarantees that's actually true (e.g. a
    non-interactive harness driving advance_simulation with nobody
    having said anything yet). The prompt below tells the host outright
    to check that assumption and ask before deciding, rather than
    silently inventing what the player did.
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
            + (
                f"\n\nWhat happens has already been decided: {decision!r} "
                f"-- record its consequences now; don't re-decide it."
                if decision else ""
            )
            + (
                f"\n\n{human_character_alias} is the player's own character, involved in "
                f"this event. If you don't already know what {human_character_alias} "
                f"actually did or said here from the conversation so far, ask them "
                f"directly before deciding what happened -- don't invent or assume "
                f"their action. If you already know it (they told you earlier in this "
                f"conversation), just use that; there's no need to ask again."
                if human_character_alias else ""
            )
        ),
        origin="resolve_event",
    )
    return await replay.resolve(request, responder=event_responder(), session=session)


async def plan_events(alias: str, replay: TurnReplay, session, character_alias: str | None = None) -> str:
    """Plan box: ask a responder whether anything new needs to be
    scheduled as a result of `alias` resolving, creating new `event` entities if so.

    Always asked, even when nothing ends up being scheduled -- "nothing
    follows from this" is this step's own answer to reach, not a case the
    loop skips based on `alias`'s outcome alone (see `process_event`).

    `character_alias`, when given (see `process_event`'s own branch),
    adds a reminder to schedule that character's own next turn if they
    have more to do -- omitted entirely for an ordinary base-module
    event, so a scenario with no characters at all (e.g. the parking
    puzzle) never sees character-turn language in its own plan prompt.
    """
    character_reminder = (
        f" -- including {character_alias}'s own next turn, if they have "
        f"more to do in this scene: schedule it the same way as anything "
        f"else, linked back via involved_entity"
        if character_alias
        else ""
    )
    request = JudgmentRequest(
        prompt=(
            f"Given how {alias} just resolved, does anything new need to "
            f"happen as a result? If so, create it now: one or more new "
            f"event entities (their own start_time/duration/event_state/"
            f"involved_entity) via update_registry{character_reminder}. If "
            f"nothing follows from this, just say so -- no new events needed."
        ),
        origin="plan_events",
    )
    return await replay.resolve(request, responder=event_responder(), session=session)


async def process_event(registrar: Registrar, alias: str, replay: TurnReplay, session) -> tuple[str, str]:
    """Process event box: Advance clock -> [Decide event] -> Resolve event -> Plan events.

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

    Decide event (`character.decide_event`) only runs when `alias`'s
    event involves an NPC-controlled character
    (`character.character_in_event`/`character_interaction_type`) -- an
    ordinary base-module event skips straight to resolve_event unchanged.
    A human-voiced character's own event also skips decide_event (there's
    nothing to autonomously decide for one), but is still flagged to
    resolve_event via `human_character_alias`, below, so that call's own
    prompt can tell the host to actually check it knows the player's
    action rather than assuming so.
    """
    end_time = advance_clock(registrar, alias)
    registrar.update(
        yaml_strings={SOURCE_KEY: f"{WORLD_CLOCK_ALIAS}:\n    - world_clock:\n        value: {end_time}\n"},
    )
    decision = None
    human_character_alias = None
    character_alias = character.character_in_event(registrar, alias)
    if character_alias is not None:
        interaction_type = character.character_interaction_type(registrar, character_alias)
        if interaction_type == "npc":
            decision = await character.decide_event(registrar, character_alias, replay, session)
        elif interaction_type == "player":
            human_character_alias = character_alias
    resolve_narration = await resolve_event(
        alias, replay, end_time, session, decision=decision, human_character_alias=human_character_alias
    )
    plan_narration = await plan_events(alias, replay, session, character_alias=character_alias)
    return resolve_narration, plan_narration


async def _run_event_loop(
    registrar: Registrar,
    session,
    *,
    resume_alias: str | None = None,
    replay: TurnReplay | None = None,
) -> tuple[str | None, TurnReplay | None, str, str | None, bool, str | None]:
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

    Returns (alias, replay, prompt, responder, is_checkpoint, origin):
    `alias`/`replay`/`responder`/`origin` are None only when the queue is
    empty (nothing left to stash); otherwise `alias`/`replay` are exactly
    what `advance_simulation` needs to encode into a `resume_token` for
    resuming this same pause point, and `responder` ("host" or "subagent",
    never "human" -- see `resolve_event`) says who it's asking.
    `is_checkpoint` passes through `NeedsExternalInput.is_checkpoint`
    (False when the queue emptied) -- see that attribute's docstring.
    `origin` passes through `NeedsExternalInput.origin` -- which of
    decide_event/resolve_event/plan_events actually raised this, so the
    caller can tell a connected host which step is asking (see
    `_wrap_loop_result`'s own `step` field).
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
                if _no_event_ever_recorded(registrar):
                    return (
                        None,
                        None,
                        "No events have ever been scheduled in this world -- there's nothing to "
                        "advance, and nothing has actually happened yet. If that's unexpected, "
                        "check that the scenario/manifest actually wrote an `event` entity "
                        "(view_registry('event') will be empty) -- this is not the same as a "
                        "world that's run its schedule to completion.",
                        None,
                        False,
                        None,
                    )
                return None, None, "Nothing scheduled.", None, False, None
            if not is_event_valid(registrar, alias):
                alias = None
                continue
            replay = TurnReplay(answers=[], deadline=deadline)
        try:
            await process_event(registrar, alias, replay, session)
        except NeedsExternalInput as e:
            return alias, replay, e.prompt, e.responder, e.is_checkpoint, e.origin
        # No exception: both resolve and plan answered fully -- reset alias
        # to force a fresh pop next iteration.
        alias = None


def _save_pending(registrar: Registrar, alias: str, answers: list[str], is_checkpoint: bool = False) -> str:
    """Persist a paused turn's resumption state into the registry, keyed to `alias`.

    Stored in the registry (Postgres), not this process's own memory and
    not encoded into the token round-tripped through the client -- still
    matches this module's own `stateless_client` mandate (see the
    `__iacs__` marker at the top: whichever subprocess/session reopens
    this world can resume identically, the same way every other piece of
    world state already survives a restart), just via the durable store
    this architecture already has for exactly that, rather than a
    `_pending_turns`-style in-memory session dict.

    Avoids a real correctness bug the prior token-encodes-everything
    design had: `answers` accumulates this event's full judgment-call
    text and only grows across checkpoints, so by a later event in a run
    it could be several KB -- a large, opaque, ever-growing blob the
    connected model had to relay back byte-for-byte on every single
    round-trip. A weaker/cheaper driver model mangling one character of
    that on the way back is exactly the failure mode that produced a raw,
    unhandled decode crash (see the fix for that in `_load_pending`
    below, and issue #75). The `resume_token` returned here is now just
    `alias` itself -- a short, already-known-safe identifier the model
    already relays correctly everywhere else in this codebase.

    `is_checkpoint` (False by default) marks a keyed_subagent budget
    check-in pause -- see `NeedsExternalInput.is_checkpoint`.
    """
    entity = {alias: [{"pending_resolution": {"answers": json.dumps(answers), "is_checkpoint": is_checkpoint}}]}
    registrar.update(
        yaml_strings={SOURCE_KEY: yaml.safe_dump(entity, sort_keys=False)},
        time=_next_time_stamp(registrar),
    )
    return alias


def _load_pending(registrar: Registrar, resume_token: str) -> tuple[str, list[str], bool]:
    """Inverse of `_save_pending`: look `resume_token` (a plain alias) up in the registry.

    Raises a clear `ValueError` if nothing was ever recorded for it (a
    tampered/invented resume_token, one from a different world/session, or
    simply a typo) instead of failing deep inside a decode step with
    nothing actionable to react to.
    """
    raw_answers = registrar.safe_view_current("pending_resolution.answers", resume_token).to_scalar()
    if raw_answers is None:
        raise ValueError(
            f"resume_token {resume_token!r} is invalid or doesn't match any paused turn in this world -- "
            "call advance_simulation with no arguments to get a fresh prompt for the current event."
        )
    is_checkpoint = bool(registrar.safe_view_current("pending_resolution.is_checkpoint", resume_token).to_scalar())
    return resume_token, json.loads(raw_answers), is_checkpoint


def _resolve_args(
    registrar: Registrar, resume_token: str | None, answer: str | None
) -> tuple[str | None, TurnReplay | None]:
    """Shared resume_token/answer validation + decode for `advance_simulation`."""
    if resume_token is None:
        if answer is not None:
            raise ValueError("answer given without resume_token -- nothing to answer yet.")
        return None, None
    if answer is None:
        raise ValueError("resume_token given without an answer.")
    alias, prior_answers, is_checkpoint = _load_pending(registrar, resume_token)
    if is_checkpoint:
        # `answer` is the check-in's own reply, not game content -- discard
        # it so the interrupted call retries fresh instead of banking it.
        return alias, TurnReplay(answers=prior_answers)
    return alias, TurnReplay(answers=[*prior_answers, answer])


def _wrap_loop_result(
    registrar: Registrar,
    alias: str | None,
    replay: TurnReplay | None,
    prompt: str,
    responder: str | None,
    is_checkpoint: bool = False,
    origin: str | None = None,
) -> dict:
    """Shared result shape for `advance_simulation`.

    `origin` (one of "decide_event"/"resolve_event"/"plan_events" -- see
    `NeedsExternalInput.origin`) becomes `step`: which of those three
    calls is actually asking, so a connected host doesn't have to infer
    that purely from the prompt's own wording.
    """
    if alias is None:
        return {"status": "done", "narration": prompt}
    return {
        "status": "input_required",
        "prompt": prompt,
        "step": origin,
        "responder": responder,
        "resume_token": _save_pending(registrar, alias, replay.answers, is_checkpoint),
    }


# Tool implementations -- `mcp_server.py`'s `@server.tool()` functions unpack
# `Context` into `session` and call these directly.


def start_world(
    session, save_dir: str, scenario_dir: str | None = None, client_trace_path: str | None = None
) -> str:
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
        client_trace_path: The connected client's own trace_path (e.g. a
            HeadlessSession's), if it wants keyed_subagent's own judgment
            calls appended to that exact same file instead of a separate
            one of their own -- see unified_trace_interface's
            single_shared_trace_file. Recorded via
            `registrar_sessions.get_trace_path`; omitted or None means
            keyed_subagent gets no trace_path at all (unchanged, prior
            behavior).
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

    registrar_sessions.set_registrar(
        session, registrar, export_dir=save_dir_path, client_trace_path=client_trace_path
    )
    return f"World opened at {save_dir_path}. Call view_registry or view_entity to see what's there."


async def advance_simulation(session, resume_token: str | None = None, answer: str | None = None) -> dict:
    """Fast-forward through any events whose end_time has been reached,
    and pause when a turn needs input story-simulator's own process can't supply.

    The event-driven simulation (see this module's own docstring): world
    state is `event` entities, each ready to resolve once world time
    reaches its own end_time -- start_time + duration
    (manifest/builtins.yaml's event_components) -- not the acting
    entities (a car, a door, ...) themselves, which carry no schedule of
    their own. Every such event goes through resolve (what happened) and
    plan (what, if anything, follows from that), each via responder="host"
    or "subagent" (see `config.event_responder`); an NPC-controlled
    character's own event gets one more call first -- decide (see
    `decide_event`), via `config.decide_responder()` -- so a fresh NPC
    event typically means three pauses in a row rather than two before
    the loop reaches the next one. A human-voiced character's own event,
    and an ordinary base-module event, both stay at two.

    Call with neither argument to start (or continue after a prior call
    finished with nothing left scheduled). That, and every later call,
    returns either ``{"status": "done", "narration": ...}`` or
    ``{"status": "input_required", "prompt": ..., "step": "decide_event" or
    "resolve_event" or "plan_events", "responder": "host" or "subagent",
    "resume_token": ...}``. `step` says which of the two-or-three calls a
    fresh/resumed event goes through (see this docstring's own paragraph
    above) is actually asking -- so it doesn't have to be inferred purely
    from `prompt`'s own wording. On the latter, decide what happens
    yourself if `responder` is "host", or follow `prompt`'s own instruction
    to delegate to an isolated subagent if it's "subagent" -- either way,
    record whatever you decide yourself via update_registry (there's no
    structured return value this tool applies on your behalf), then call
    again with that exact `resume_token` and your `answer` -- no separate
    tool. `resume_token` is just the paused event's own alias; its actual
    resumption state (the answers given so far) lives in the registry, not
    encoded into the token itself (see `_save_pending`/`_load_pending`) --
    so, same as before, there's no *process* state to lose: this survives
    an MCP disconnect/reconnect between calls, or even a fresh subprocess
    after a restart, the same way every other piece of world state already does.

    Args:
        resume_token: The `resume_token` from this session's last
            `input_required` result, or omitted to start/continue fresh.
        answer: Your answer to that result's `prompt` -- what an event's
            resolution was, or what (if anything) it schedules next,
            recorded via update_registry before you answer. Omit `answer`
            itself along with `resume_token` on a fresh call.
    """
    registrar = registrar_sessions.get_registrar(session)
    resume_alias, replay = _resolve_args(registrar, resume_token, answer)
    alias, replay, prompt, responder, is_checkpoint, origin = await _run_event_loop(
        registrar, session, resume_alias=resume_alias, replay=replay
    )
    return _wrap_loop_result(registrar, alias, replay, prompt, responder, is_checkpoint, origin)
