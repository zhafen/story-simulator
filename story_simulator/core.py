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
        "The pop_event/is_event_valid/advance_clock/resolve_event/plan_events "
        "functions just live loose at module scope here. Evaluate whether "
        "the event loop deserves a more deliberate structure (a class, a "
        "dataclass-based state object, an explicit stage protocol) as more "
        "modules start hooking into it, instead of a flat function bag."
    ),
    "solution of": "story_simulator_mission.stateless_client",
}

import base64
import difflib
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
# process_event from the popped event's own start_time + duration (see
# advance_clock: "the popped event's own end_time becomes 'now' for this
# turn") and read by _next_time_stamp for every write anything does while
# resolving that event's turn, so "how recent is this row" and "when this
# event's end_time was reached" share one clock instead of the wall clock.
# Session-scoped process memory, not persisted -- a subprocess restart
# mid-turn resets it to 0.0 until the next event pop re-derives it, a
# known gap (see docs/manifest/story-simulator.yaml: world_time_concept)
# accepted for now in favor of not introducing a separate persisted clock
# entity.
_current_world_time: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


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


# ---------------------------------------------------------------------------
# Event-driven simulation loop -- one function per box in the turn-anatomy
# diagram (see docs/architecture.md). The schedule is `event` entities'
# own start_time/duration (manifest/builtins.yaml's event_components),
# not an in-memory priority queue and not a next_due component rescheduled
# by code -- an event's timing is set once, either by whoever pre-plans it
# or by a responder's own `plan_events` call, and never revised afterward.
# ---------------------------------------------------------------------------

_TERMINAL_EVENT_STATES = ("complete", "interrupted")


def pop_event(registrar: Registrar) -> str | None:
    """Pop event box: whichever `event` entity's end_time comes soonest, or
    None if nothing is currently scheduled.

    An event only enters consideration once it has both start_time and
    duration set -- one not yet scheduled (event_state "not started", or
    no event_state row at all yet) isn't a candidate, the same way an
    entity with no next_due row wasn't under the mechanism this replaces.
    A terminal event (event_state "complete" or "interrupted") is filtered
    out the same way an inf-valued next_due used to be. end_time is
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
    """Advance clock box: the popped event's own start_time + duration --
    its end_time, the moment it actually resolves, not when it started --
    becomes "now" for this turn.

    No separate persisted global clock -- the popped event's own timing
    is the only notion of "current time" needed today.
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
    event's own start_time + duration (see `advance_clock`) -- every write
    made while resolving one event's turn shares that same "now", the
    same world-time axis `event.start_time`/`event_state.time`/`outcome`
    writes all use, rather than a wall-clock substitute. Falls back to 0.0
    if nothing has been popped yet for this session (e.g. a stray
    `update_registry` call before `advance_simulation` is ever run).

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

    A straight, mechanical round-trip (`Registrar.export_manifest`), run
    after every registry write so a save's own YAML reads as a live
    mirror of the registry rather than frozen turn-zero seed data. See
    docs/manifest/history.yaml: project_history.turn_pipeline_removed and
    .world_yaml_sync_reverses_old_archivist_design for why this replaced
    the old LLM-driven Archivist read/write loop.

    Writes to two directories, not one:
    - `world/`: current state, collapsed -- a time_dimension'd component
      type shows only its current row per entity, not every restatement.
    - `world_history/`: the same content, uncollapsed -- full change
      history, since the registry keeps it forever but it would
      otherwise only exist in this process's own DB connection.

    Each is a directory, not a fixed filename, so a save can be split
    across multiple files later -- see docs/manifest/history.yaml:
    project_history.world_save_format_switched_from_fixed_filenames_to_directories.

    Also re-exports the field-schema manifest to its own `builtins.yaml`
    alongside `world.yaml`; deleted rather than left to accumulate, since
    it's static schema, not game state.
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


def _find_malformed_entities(yaml_string: str) -> list[str]:
    """Scan for entities whose components aren't given as a YAML list --
    the shape iacs's EC parser requires. A component written as a bare
    mapping under an alias (`alias:\\n    component:\\n        value: x`
    instead of the required list form, `alias:\\n    - component:\\n
    value: x`) is silently accepted by `registrar.update()` -- no error,
    no `invalid_field` row -- yet merges nothing at all, confirmed
    happening live: a responder had no signal its own write never took
    effect (an event's own lifecycle transition never actually recorded,
    so the event loop kept re-popping the same event forever).
    `_update_registry_and_sync` raises on whatever this finds, before
    ever merging, so that mistake surfaces as an ordinary tool error the
    caller can react to instead.

    A dict value is ambiguous on its own: it's either a malformed
    component list (the mistake above) or a legitimate nested-entity dict
    (each key its own child entity, e.g.
    tests/data/scenarios/move/scenario.yaml's `journaling_desk`, whose
    sub-keys are themselves proper component lists). Distinguished here
    by recursing only when *every* value at this level is itself a list
    or dict -- a bare scalar anywhere means this level was meant as a
    component list, not further nesting. `"data"` is skipped everywhere,
    matching EC's own freeform-notes convention (never itself a component
    list).

    Best-effort: a parse failure or an unexpected top-level shape just
    finds nothing rather than raising here -- `registrar.update()`'s own
    error handling is authoritative for those, this only adds a check for
    the one silent-failure mode it has none for.
    """
    try:
        parsed = yaml.safe_load(yaml_string)
    except yaml.YAMLError:
        return []
    if not isinstance(parsed, dict):
        return []

    malformed: list[str] = []

    def check(path: str, value) -> None:
        if isinstance(value, list):
            return
        if isinstance(value, dict) and value and all(
            isinstance(v, (list, dict)) for k, v in value.items() if k != "data"
        ):
            for key, sub_value in value.items():
                if key != "data":
                    check(f"{path}.{key}", sub_value)
            return
        malformed.append(path)

    for alias, value in parsed.items():
        if alias != "data":
            check(alias, value)
    return malformed


def _referenced_component_types(parsed: dict) -> set[str]:
    """Collect every component-type name referenced anywhere in `parsed`
    (already-`yaml.safe_load`-ed entity-first YAML) -- the component-list
    keys/bare-string markers at whatever nesting depth they actually
    appear, not the entity-path segments above them.

    Mirrors `_find_malformed_entities`'s own traversal: recurse through
    dict-of-dicts-or-lists (entity nesting), and once an actual list is
    reached (a component list), that's where real component-type names
    live -- either a bare string marker (e.g. `component_type`) or the
    single key of a one-key dict (e.g. `{"location": {"value": ...}}`).
    Assumes `parsed` is already well-formed (no bare-mapping mistakes) --
    call this only after `_find_malformed_entities` finds nothing.
    """
    types: set[str] = set()

    def walk(value) -> None:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    types.add(item)
                elif isinstance(item, dict):
                    types.update(k for k in item if k != "data")
            return
        if isinstance(value, dict):
            for key, sub_value in value.items():
                if key != "data":
                    walk(sub_value)

    for alias, value in parsed.items():
        if alias != "data":
            walk(value)
    return types


def _component_types_defined_inline(parsed: dict) -> set[str]:
    """Names of component types being freshly declared in this same YAML
    batch -- an entity named after the type itself, carrying a bare
    `component_type` marker in its own component list, the same shape
    manifest/builtins.yaml's own definitions use (see CLAUDE.md's "Define
    a component type's schema..." section): `location:\n    -
    description: ...\n    - component_type\n    - field: ...`.
    """
    defined: set[str] = set()
    for alias, value in parsed.items():
        if alias == "data" or not isinstance(value, list):
            continue
        if any(item == "component_type" for item in value):
            defined.add(alias)
    return defined


def _find_component_named_as_nested_entity(yaml_string: str, known: set[str]) -> list[str]:
    """Scan for an alias whose value is a dict (`_find_malformed_entities`'s
    "legitimate nested-entity" shape) where one of that dict's own keys
    names an already-known, real component type -- e.g.
    `car_b:\n    location:\n        - value: x` (missing the leading `- `
    that would make `location` a list item, i.e. a component attachment,
    rather than a dict key, i.e. a nested child entity's own alias).
    Confirmed live: iacs's parser reads this shape as "car_b has a nested
    child entity named `location`", not "attach a `location` component to
    car_b" -- structurally identical to a genuine nested entity (e.g.
    tests/data/scenarios/move/scenario.yaml's journaling_desk/desk/journal),
    so `_find_malformed_entities` doesn't, and structurally can't on shape
    alone, catch it.

    Mechanical, not semantic, like `_find_unknown_component_types`: a
    nested child entity's alias coinciding with a real component type's
    name is vanishingly unlikely to be intentional, so this flags every
    such collision -- see docs/manifest/history.yaml: project_history.
    nested_component_name_collision_check_added.

    Only checks nesting one level below a top-level alias, matching the
    one live mistake actually observed -- not a general recursive walk
    like `_find_malformed_entities`'s own disambiguation, since a
    collision at a deeper nesting level has no evidence behind it yet.
    """
    try:
        parsed = yaml.safe_load(yaml_string)
    except yaml.YAMLError:
        return []
    if not isinstance(parsed, dict):
        return []

    suspicious: list[str] = []
    for alias, value in parsed.items():
        if alias == "data" or not isinstance(value, dict):
            continue
        for key, sub_value in value.items():
            if key != "data" and key in known and isinstance(sub_value, list):
                suspicious.append(f"{alias}.{key}")
    return suspicious


def _find_unknown_component_types(yaml_string: str, known: set[str]) -> dict[str, list[str]]:
    """Component types this write references that aren't in `known` and
    aren't being defined inline (see `_component_types_defined_inline`) --
    mapping each unknown name to its closest known matches, if any, so the
    caller's own error message can suggest a likely-intended real name
    instead of leaving the caller to guess again.

    Best-effort like `_find_malformed_entities`: a parse failure or
    unexpected top-level shape just finds nothing here too, since
    `registrar.update()`'s own error handling is authoritative for those.

    Deliberately mechanical, not semantic -- catches an invented name
    (`parked_at`) that was never declared anywhere, but not a real,
    already-declared type used for the wrong purpose (e.g. writing a
    car's location under `todo` instead of `location` -- both are
    genuine, known component types, so this check has nothing to object
    to). See docs/manifest/history.yaml: project_history.
    mechanical_component_type_validation_added for that scope decision.
    """
    try:
        parsed = yaml.safe_load(yaml_string)
    except yaml.YAMLError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    referenced = _referenced_component_types(parsed)
    defined_inline = _component_types_defined_inline(parsed)
    unknown = referenced - known - defined_inline
    if not unknown:
        return {}
    return {name: difflib.get_close_matches(name, known, n=3) for name in sorted(unknown)}


def _update_registry_and_sync(registrar: Registrar, save_dir: Path, yaml_string: str, session) -> None:
    """Merge `yaml_string` into the registry, then sync `save_dir`'s YAML to match.

    Three checks before merging at all -- see `_find_malformed_entities`
    for the first. The second, `_find_component_named_as_nested_entity`,
    rejects a write where a known component type's name appears as a
    nested dict key instead of a component-list item -- a shape
    `_find_malformed_entities` can't distinguish from legitimate entity
    nesting on structure alone. The third, `_find_unknown_component_types`,
    rejects a write that references a component type nothing has ever
    declared, unless that same write also declares it (see
    `_component_types_defined_inline`) -- a mechanical backstop against
    the recurring live-test bug where a weak model invents a plausible
    but nonexistent component name (`parked_at`, `parking_location`)
    instead of using the real, already-declared one (`location`),
    independent of whether it ever bothers to check first via
    view_entity/view_registry.
    """
    malformed = _find_malformed_entities(yaml_string)
    if malformed:
        raise ValueError(
            "Each entity's components must be a YAML list (a leading `- ` before each "
            "component name), e.g. `alias:\n    - component:\n        value: x` -- a bare "
            "mapping (`alias:\n    component:\n        value: x`) is silently ignored "
            f"rather than merged. Malformed here: {', '.join(malformed)}."
        )

    known = set(registrar.registry.known_component_types)

    nested = _find_component_named_as_nested_entity(yaml_string, known)
    if nested:
        raise ValueError(
            "Found a real component type used as a nested dict key instead of a "
            "component-list item, which iacs parses as a nested child entity, not a "
            f"component attachment: {', '.join(nested)}. If you meant to attach that "
            "component, use the list form instead, e.g. `alias:\n    - component:\n"
            "        value: x` rather than `alias:\n    component:\n        - value: x`. "
            "If you genuinely meant a nested child entity that happens to share a name "
            "with a real component type, rename it to something unambiguous."
        )

    unknown = _find_unknown_component_types(yaml_string, known)
    if unknown:
        details = "; ".join(
            f"{name!r} (did you mean {' or '.join(repr(c) for c in candidates)}?)"
            if candidates
            else f"{name!r} (no similar existing component type found)"
            for name, candidates in unknown.items()
        )
        raise ValueError(
            f"Unknown component type(s): {details}. Check view_entity/view_registry for "
            "the real one before guessing a name. If this is genuinely a new component "
            "type, define it in this same write: an entity named after the type itself, "
            "with a `component_type` marker and a `field:` block describing each field "
            "(see manifest/builtins.yaml for examples, e.g. `location`)."
        )

    registrar.update(
        input_dirs=[str(MANIFEST_DIR)],
        yaml_strings={WORLD_FILE_ID: yaml_string},
        time=_next_time_stamp(session),
    )
    _export_world_yaml(registrar, save_dir)


# ---------------------------------------------------------------------------
# Turn resolution
# ---------------------------------------------------------------------------


async def resolve_event(alias: str, replay: TurnReplay, end_time: float) -> str:
    """Resolve box: ask a responder to interpret `alias` now that its
    end_time has been reached, and hand back whatever it says, for
    narration.

    No next_due_in convention to parse here, unlike the mechanism this
    replaces: the responder is expected to record everything itself via
    update_registry -- this event's own `outcome`, this event's own
    `event_state` transition (complete or interrupted), and whatever it
    changes about the entities it involves (see involved_entity) -- the
    same direct tool-calling pattern it already uses for every other
    write. The prompt spells out that last part explicitly (write changes
    onto the affected entity itself, not just described in this event's
    own outcome text) -- confirmed live that a weak model otherwise
    narrates an involved entity's new state inside the event's outcome
    without a separate update_registry write for that entity, leaving
    nothing for a caller reading that entity directly to find. This
    function's only job is to ask and hand back the answer;
    persisting is entirely the responder's own, not a return value this
    code applies on its behalf (see `plan_events`, and `process_event`'s
    own docstring for why there's no separate mechanical "update" step).

    Doesn't name a specific component type (e.g. `location`) as an
    example, even though that's what most scenarios so far have needed:
    this prompt is generic across every scenario, and not every event's
    consequence is a location change, so hardcoding one component here
    would bias every scenario toward it. Points at `view_entity` on the
    component type's own name instead (its field descriptions carry
    scenario-specific examples, e.g. `location`'s own doubles as the
    phrasing convention) -- confirmed live that a model resolving its
    first-ever write to an unfamiliar component type doesn't otherwise
    think to look up that component type's own schema, and improvises a
    reasonable-but-inconsistent phrasing instead.

    `end_time` (the same value `process_event` just fed to `advance_clock`
    -- `alias`'s own start_time + duration, plain arithmetic, not left for
    the responder to infer) is stated explicitly in the prompt: confirmed
    live that a weak model otherwise sometimes reads a due-style ("X is
    due") framing against start_time alone (i.e. when the trip *starts*)
    rather than start_time + duration (when it actually *arrives*),
    misjudging which other events have already resolved by that point --
    part of why this uses "end_time" rather than "due" throughout, not
    just here.

    The prompt also states outright that nothing with an earlier end_time
    is still unresolved -- `pop_event`'s own sort guarantees this is the
    earliest-end_time event still pending, so nothing else has resolved
    yet either. Confirmed live that, without this stated explicitly, a
    weak model sometimes assumes a *different*, not-yet-resolved entity's
    event has already happened -- reasoning from that other event's
    start_time or its row's position in a table instead of
    checking its actual `event_state` -- and writes a wrong outcome for
    `alias` on top of that wrong assumption (e.g. deciding a shared
    resource a different car "already took" is unavailable, when that
    other car's own trip hasn't resolved at all). Deliberately points at
    checking `event_state` itself (already the one place this loop
    records whether an event is done) rather than adding a second,
    redundant field elsewhere for the same fact.

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
    return await replay.resolve(request, responder=event_responder())


async def plan_events(alias: str, replay: TurnReplay) -> str:
    """Plan box: ask a responder whether anything new needs to be
    scheduled as a result of `alias` resolving, and let it create new
    `event` entities via update_registry if so.

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
    return await replay.resolve(request, responder=event_responder())


async def process_event(registrar: Registrar, alias: str, replay: TurnReplay, session) -> tuple[str, str]:
    """Process event box: Advance clock -> Resolve event -> Plan events.

    No update-data step: `resolve_event` and `plan_events` both write
    everything they decide directly via update_registry (including
    `alias`'s own event_state transition), so there's nothing left for
    this function to persist mechanically afterward -- unlike the
    next_due_in mechanism this replaces, which needed a code-driven
    predict/push reschedule step because a plain float answer had nothing
    else able to act on it.
    """
    end_time = advance_clock(registrar, alias)
    _current_world_time[session] = end_time
    resolve_narration = await resolve_event(alias, replay, end_time)
    plan_narration = await plan_events(alias, replay)
    return resolve_narration, plan_narration


async def _run_event_loop(
    registrar: Registrar,
    session,
    *,
    resume_alias: str | None = None,
    replay: TurnReplay | None = None,
) -> tuple[str | None, TurnReplay | None, str, str | None]:
    """The Event-driven simulation subgraph itself: Pop event -> Valid? ->
    Process event (which itself advances the clock first, then asks two
    separate responder calls -- resolve, then plan), looping until either
    a NeedsExternalInput pauses it (returned to the caller, not raised
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
        # No exception: both resolve and plan answered fully -- reset
        # alias to force a fresh pop next iteration. Each one always
        # pauses at least once (responder="host" or "subagent", per
        # config.event_responder() -- never "human", see resolve_event)
        # unless this exact call was already answered by a prior replay.
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

    The returned message also mentions iacs's own `load_database` tool
    (mcp__iacs__*, if connected) as an optional extra: pointing it at this
    exact registry_url lets its deeper introspection (validate_yaml,
    describe_format, ...) operate on this world instead of iacs's own
    unrelated example manifest. Not required for ordinary reads any more --
    view_registry/view_entity (below) cover that directly, via the same
    underlying Registrar methods iacs's own tools use, so there's no
    separate MCP server a host needs to discover just to look something
    up. (An earlier version of this removed view_registry/view_entity
    entirely in favor of requiring iacs's tools instead -- reverted before
    that specific "required first step" framing was ever live-verified,
    on the strength of prior evidence already in hand: across every live
    rerun so far, a weak model has reliably discovered and used tools
    already on this server, but never once discovered or called a tool on
    a *separate* MCP server, nudged or not; see docs/manifest/history.yaml:
    project_history.story_simulator_view_tools_reinstated_as_iacs_delegates.)

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

    # Declares the manifest's own component-type schemas (location, event,
    # ...) on this registrar object regardless of whether this was a fresh
    # or resumed save, or whether the branch above already did it once --
    # a declared-but-dataless schema lives only in a Registry's own
    # in-memory state (Registry.declare_schema's docstring), never
    # persisted as a physical table, so it doesn't survive a reconnect on
    # its own (e.g. a resumed save whose player never happened to use
    # `location` before disconnecting). Without this, the first write to
    # an already-declared-but-not-yet-used type would look "unknown" to
    # _find_unknown_component_types even though it's perfectly legitimate.
    registrar.update(input_dirs=[str(MANIFEST_DIR)])

    _registrars[session] = registrar
    _save_dirs[session] = save_dir_path
    return (
        f"World opened at {save_dir_path}. Component types: {registrar.registry.component_types}. "
        "Call view_registry or view_entity to see what's there. "
        f"If iacs's own tools are also available (mcp__iacs__*) and you want its deeper "
        f"introspection (validate_yaml, describe_format, ...), call its load_database with "
        f"database_url={registry_url(save_dir_path)!r} to point them at this exact world too -- "
        f"optional, not required for ordinary reads."
    )


def view_registry(session, component_type: str) -> str:
    """View all recorded data for one component type (e.g. "position", "object", "character").

    Covers both the starting scenario and everything recorded since, since
    it reads straight from the registry -- the same `view_df` method
    iacs's own `view_component` tool wraps too (see this module's own
    docstring history for why this exists as a story-simulator tool
    at all rather than relying on iacs's copy: docs/manifest/history.yaml,
    project_history.story_simulator_view_tools_reinstated_as_iacs_delegates).
    Rendered as a markdown table, not CSV -- published format comparisons
    put CSV among the worst-parsed formats for LLMs, which is what
    actually reads this (the responder standing in for this call), not
    another program.
    """
    registrar = _get_registrar(session)
    return registrar.view_df(component_type).fillna("null").to_markdown()


def view_entity(session, entity_id: str) -> str:
    """Return every recorded component instance for a specific entity.

    Delegates straight to iacs's own `Registrar.view_entity` -- the same
    entity-traversal logic iacs's own `view_entity` tool already wraps,
    not reimplemented here a second time (an earlier version of this
    function did reimplement it independently; see docs/manifest/
    history.yaml: project_history.
    story_simulator_view_tools_reinstated_as_iacs_delegates for why that
    changed).

    Args:
        entity_id: Entity hash, alias, or unambiguous path fragment (e.g.
            "player", "desk", or "journaling_desk.desk").
    """
    registrar = _get_registrar(session)
    return registrar.view_entity(entity_id, format="markdown")


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
    """Fast-forward through any events whose end_time has been reached,
    and pause whenever a turn needs input only outside story-simulator's
    own process can supply.

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
    next one. No character/NPC concept at all. (A character-aware branch
    used to layer player/NPC turns on top of an earlier, next_due-based
    version of this loop; moved out to `shelved/` pending a rewrite -- see
    `docs/architecture.md`.)

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
    registrar = _get_registrar(session)
    resume_alias, replay = _resolve_args(resume_token, answer)
    alias, replay, prompt, responder = await _run_event_loop(
        registrar, session, resume_alias=resume_alias, replay=replay
    )
    return _wrap_loop_result(alias, replay, prompt, responder)
