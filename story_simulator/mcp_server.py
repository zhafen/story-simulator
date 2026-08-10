"""MCP server exposing story-simulator's world-state and narrative tools.

story-simulator is *just* this server — there is no in-process agent loop
here. `advance_simulation` runs one event-driven simulation loop (see
`_run_event_loop`) regardless of which optional modules are active
(`story_simulator.config.enabled_modules`): with the character module,
`process_event`/`character_communication`/`resolve_event` and
`story_simulator.spatial`'s character-aware `pop_event`; with it off,
`process_base_event` and `story_simulator.core`'s base
`pop_event`/`predict_event`/`push_event`. Either way, the loop
fast-forwards through anything it can resolve on its own, and pauses
whenever a turn needs input only the connected host can supply -- the
player-voiced character's action/resolution, an NPC's decision (if no
subagent key is configured), or a base-module entity's own resolution --
handing control back to whatever MCP-aware host is connected. That host
IS the narrator: it perceives what's going on from the returned prompt,
relays it to a human or decides it itself, calls
`generate_terrain`/`resolve_physics` when it needs a specialist's
judgment, narrates directly in its own replies, and calls
`advance_simulation` again with its decision and the `resume_token` it
was given, to resume the loop -- Multi Round-Trip Requests (MRTR, MCP
spec 2026-07-28), not a second dedicated tool.
`perceive`/`view_registry`/`view_entity`/`update_registry` remain
directly callable too. `advance_npc_turn` is a thin wrapper over the same
`process_event` used internally by the character module's own branch,
forced onto one named NPC.

The judgment resolver behind all of this (`story_simulator.resolve`) is
what lets `character_communication`/`resolve_event`/`resolve_base_event`
reach a real decision from any nesting depth without every intervening
function having to be a generator -- see that module's docstring.

Structurally mirrors `iacs/iacs/mcp_server.py`: a session-scoped `Registrar`
kept in a `weakref.WeakKeyDictionary` (cleaned up automatically once the
session ends), plain `@server.tool()` functions, `server.run(transport="stdio")`.
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

from story_simulator import core, spatial
from story_simulator.agents import AgentSpec, run_tool_loop
from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    MANIFEST_DIR,
    WORLD_FILE_ID,
    enabled_modules,
    registry_schema_name,
    registry_url,
    resolve_anthropic_api_key,
    resolve_database_dsn,
)
from story_simulator.resolve import JudgmentRequest, NeedsExternalInput, TurnReplay
from story_simulator.specialists import PhysicsAgent, TerrainAgent

PROD_NPC_CONFIG_PATH = Path(__file__).parent / "npc.yaml"
PROD_NPC_RESOLVER_CONFIG_PATH = Path(__file__).parent / "npc_resolver.yaml"
MAX_NPC_TURN_TOOL_TURNS = 8
# save_dir's two export subdirectories, each holding one EC yaml file per
# original source (currently always one, since WORLD_FILE_ID is shared) --
# directories, not fixed filenames, so a save can be split across as many
# files as its author wants; the loader (see start_world) recurses into
# whichever one it picks.
WORLD_DIRNAME = WORLD_FILE_ID
WORLD_HISTORY_DIRNAME = "world_history"

_registrars: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_save_dirs: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# World time (seconds since world creation), per session -- set in
# _run_event_loop from the popped entity's own `next_due` and read by
# _next_time_stamp for every write while resolving that entity's turn, so
# "how recent is this row" and "when is X next due" share one clock.
# Session-scoped process memory, not persisted -- a subprocess restart
# mid-turn resets it to 0.0 until the next entity pop re-derives it, a
# known gap (see docs/manifest/story-simulator.yaml: world_time_concept).
_current_world_time: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# The last stamp _next_time_stamp actually handed out, per session -- lets
# it nudge apart same-world-time writes (see _next_time_stamp) instead of
# handing out the same value repeatedly.
_last_time_stamp: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
# Tie-breaking nudge for _next_time_stamp -- a whole 1, not a fraction of a
# second; see that function's docstring for why.
_TIE_EPSILON = 1

_npc_spec = AgentSpec.from_yaml(PROD_NPC_CONFIG_PATH)
_npc_resolver_spec = AgentSpec.from_yaml(PROD_NPC_RESOLVER_CONFIG_PATH)
_terrain_agent = TerrainAgent()
_physics_agent = PhysicsAgent()

_NPC_RESOLVER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_terrain",
            "description": "Invent environment/terrain details for a location with none established yet.",
            "parameters": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_physics",
            "description": "Work out the plausible physical outcome of an action.",
            "parameters": {
                "type": "object",
                "properties": {"scenario": {"type": "string"}},
                "required": ["scenario"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_data",
            "description": (
                "Merge entity-first YAML into the world registry, and state how much "
                "in-world time this action took before this entity is next due."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "yaml_string": {"type": "string"},
                    "next_due_in": {
                        "type": "number",
                        "description": (
                            "How much in-world time, in seconds, this action took."
                        ),
                    },
                },
                "required": ["yaml_string", "next_due_in"],
            },
        },
    },
]

# The player-voiced path only has one free-text answer channel, unlike
# the NPC path's typed update_data(next_due_in=...) tool parameter -- so
# resolve_event's ask for a human asks for next_due_in as a trailing text
# line instead, parsed back out by _parse_next_due_in.
_NEXT_DUE_IN_INSTRUCTION = (
    "End your answer with a line formatted exactly as `next_due_in: <seconds>` "
    "stating how much in-world time this action took."
)

# Unlike the character module's instruction above, omitting the
# next_due_in line is meaningful here -- it's how a base-module event
# tells the loop it's done (see resolve_base_event's default=inf).
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
    entity's own `next_due` -- every write made while resolving one
    entity's turn shares that same "now" rather than a wall-clock
    substitute. Falls back to 0.0 if nothing has been popped yet for this
    session.

    Two writes at the same world time would otherwise tie, since
    Registry.view_current's tie handling is presently arbitrary (iacs's
    own _seq write-order column, zhafen/iacs#94, isn't merged yet). Nudged
    apart here by _TIE_EPSILON instead, so a later write always gets a
    strictly higher stamp and "most recent write wins" still holds -- a
    stopgap to drop once #94 merges.

    _TIE_EPSILON is a whole 1, not a fraction of a second: `math.nextafter`'s
    smallest step from 0.0 lands in subnormal-float range, which the
    registry's duckdb/ibis pipeline was seen flushing back to 0.0; and
    this same stamp backfills `description.time`, an iacs builtin declared
    `type: int`, which truncates any fractional nudge to nothing. A
    whole-integer nudge survives both.
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

    Only called on a localhost DSN that just failed with
    connection-refused (see `_ensure_postgres_running`) -- never manages
    a remote server. Tries whichever service-control command this install
    has; the caller's own follow-up connection attempt determines success.
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

    Only reached from `_ensure_postgres_running` after this call just
    started a previously-unreachable local server and it's rejecting the
    default DSN's password -- a brand-new cluster with no password set
    yet, not a deliberately configured server. Runs the ALTER as the
    `postgres` OS/DB user over the Unix socket (peer-authenticated, no
    password needed for this step), the same way a human operator would
    from the shell.
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

    Dev convenience only: intervenes solely for a localhost DSN whose
    server isn't listening at all (connection refused) -- "nobody has
    started Postgres in this environment yet." Any other failure,
    including a reachable server rejecting these credentials, surfaces
    via `_ensure_postgres_schema`'s own connection attempt instead.
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

    The one Postgres-specific piece of this file -- everywhere else talks
    to the registry only through `config.registry_url`/`Registrar`,
    backend-agnostic via `ibis.connect`. `CREATE SCHEMA` is a one-off
    admin statement, not registry data, so it's a plain psycopg
    connection. Has to run before `Registrar.load` connects with that
    schema name: an unknown schema fails silently rather than erroring
    (see `config.registry_url`).
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
        "run as an event-driven simulation (one character due at a time, scheduled by its "
        "own next_due) rather than a fixed per-turn loop.\n\n"
        "Call start_world once, at the beginning, to open or seed a save. Then call "
        "advance_simulation with no arguments: it fast-forwards through any due NPCs "
        "entirely on its own, and pauses whenever it needs something only you can supply, "
        "returning {\"status\": \"input_required\", \"prompt\": ..., \"responder\": ..., "
        "\"resume_token\": ...}. `responder` is \"human\" for the player-voiced character's "
        "own turn -- what they perceive and what's being asked of them -- or \"host\" for an "
        "NPC's turn when no subagent key is configured to decide it automatically; either "
        "way, decide the answer yourself (as the player would, or as that NPC would).\n\n"
        "Decide what happens to whatever it's asking about -- call generate_terrain if the "
        "action reaches somewhere with no established terrain yet, or resolve_physics if the "
        "outcome isn't obvious (a fall, a jump, a thrown object, a collision, structural "
        "collapse) -- then call advance_simulation again with that exact resume_token and "
        "your answer to resume the loop. It will keep asking (for a \"human\" turn: first for "
        "the player's action, then separately for how that action resolves -- state the "
        "outcome and end that second answer with a line formatted exactly as "
        "`next_due_in: <seconds>`) and fast-forwarding through NPCs again until either it "
        "needs you once more (a new resume_token each time -- always use the one from the "
        "latest result) or the schedule empties (\"status\": \"done\"). Narrate every human "
        "turn's outcome directly to the character, one or two sentences, addressing them "
        "directly. Stay fully in-world: never break character, mention tools, or use "
        "metaphors or similes — describe things directly and literally.\n\n"
        "Record what happened yourself via update_registry (new positions, new entities, "
        "changed details — reusing existing aliases; attach new data to an existing entity "
        "via a `same_as` component rather than creating a disconnected duplicate). If the "
        "action puts the character at the same place as an existing entity, use that "
        "entity's exact recorded coordinates rather than recomputing a new position from an "
        "approximate stated distance. `description` and `state` are both current-value "
        "components: a new write becomes the entity's current one for perceive and for the "
        "save's exported YAML (older writes stay recorded as history — view_entity still "
        "shows all of them). Write the whole updated description each time, not a diff, and "
        "use `state` for a short current status word or phrase (e.g. a door being \"open\") "
        "rather than folding it into the description text.\n\n"
        "Use view_registry/view_entity to look up what's already known before deciding — "
        "don't invent entities or details nothing has established.\n\n"
        "perceive/update_registry/advance_npc_turn remain directly callable outside the "
        "simulation loop too (advance_npc_turn resolves one named NPC's turn on its own, "
        "the same way the loop's own NPC fast-forwarding does) — reach for advance_simulation "
        "as the default, and these when you need something outside that loop."
    ),
)


@server.tool()
def start_world(save_dir: str, ctx: Context, scenario_dir: str | None = None) -> str:
    """Open a world save for this session, seeding it from `scenario_dir` if it's empty.

    The loose seed *.yaml under save_dir is only merged into the registry
    the first time this save_dir is opened (a brand-new schema has no
    component types yet) -- a resumed save's accumulated state already
    lives in the persisted registry.

    Args:
        save_dir: Directory holding (or to hold) this world's save data.
        scenario_dir: Starting scenario to seed a brand-new save_dir from
            (an EC directory, e.g. containing scenario.yaml). Defaults to
            story-simulator's plain default world. Ignored if save_dir
            already has any save data.
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
        # Load exactly one of world_history/ / world/ / everything under
        # save_dir, in that preference order, rather than combining more
        # than one -- concatenating redundant sources risks silently
        # discarding data (YAML's last-key-wins on duplicate top-level
        # keys). See CLAUDE.md for the full reasoning.
        history_dir = save_dir_path / WORLD_HISTORY_DIRNAME
        world_dir = save_dir_path / WORLD_DIRNAME
        found = (
            (_yaml_files(history_dir) if history_dir.is_dir() else [])
            or (_yaml_files(world_dir) if world_dir.is_dir() else [])
            or _yaml_files(save_dir_path)
        )
        if found:
            # Merged as one WORLD_FILE_ID-keyed string, not input_dirs
            # (which would key each file by its own path) -- see
            # WORLD_FILE_ID's comment.
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

    A straight, mechanical round-trip (`Registrar.export_manifest`), not
    the old `IacsArchivist`'s LLM-driven read/write loop -- see
    docs/manifest/history.yaml: project_history.turn_pipeline_removed.
    Runs after every registry write so a save's own YAML stops being
    frozen turn-zero seed data and instead mirrors the registry live. See
    CLAUDE.md for the full world/world_history export format.

    `export_manifest` also re-exports this project's own field-schema
    manifest to its own `builtins.yaml` alongside `world.yaml` -- a
    normalized round-trip of `manifest/builtins.yaml`'s static content,
    not game state, so it's deleted rather than left to accumulate.
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


@server.tool()
def perceive(reference_alias: str, ctx: Context) -> str:
    """Return what `reference_alias` can currently perceive, and record it.

    Each nearby entity's own visibility distance is computed from its
    `size` component (meters), not a single flat cutoff for everyone -- a
    mountain stays perceptible from far further away than a dropped coin
    (see `story_simulator.spatial.perceptible_entities`/`game_config`).

    Tags each perceived entity `active` (replacing whatever was previously
    tagged active) and merges them into `reference_alias`'s permanent
    `memory`.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.perceive"}
    registrar = _get_registrar(ctx)
    return spatial.narrate_to_character(registrar, reference_alias)


@server.tool()
def generate_terrain(description: str) -> str:
    """Invent environment/terrain details for a location with nothing established yet.

    Args:
        description: What's already known about the location (position,
            nearby entities, how the character got there) to generate
            terrain consistent with.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.generate_terrain"}
    return _terrain_agent.generate(description)


@server.tool()
def resolve_physics(scenario: str) -> str:
    """Work out the plausible outcome of an action whose physical result isn't obvious.

    A fall, a jump, a collision, a thrown or dropped object, structural
    collapse — anything you shouldn't just decide yourself.

    Args:
        scenario: The attempted action and whatever entity state (sizes,
            distances, positions) bears on whether/how it succeeds.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.resolve_physics"}
    return _physics_agent.resolve(scenario)


@server.tool()
async def advance_npc_turn(npc_alias: str, ctx: Context) -> str:
    """Decide, narrate, and record one NPC's turn, since nobody is chatting to drive it directly.

    Args:
        npc_alias: The NPC's own alias (its `character.interaction_type`
            should be "npc").
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.advance_npc_turn"}
    registrar = _get_registrar(ctx)
    save_dir = _get_save_dir(ctx)
    # Thin wrapper over process_event, forced onto npc_alias -- an NPC's
    # whole turn never yields (nobody real is behind one), so a throwaway
    # TurnReplay with no prior answers always runs straight through.
    replay = TurnReplay(answers=[])
    return await process_event(registrar, save_dir, npc_alias, replay, ctx)


def _parse_next_due_in(answer: str, default: float = 1.0) -> tuple[str, float]:
    """Split a resolve_event answer into (narration, next_due_in).

    Looks for a trailing `next_due_in: <seconds>` line (see
    `_NEXT_DUE_IN_INSTRUCTION`) and falls back to `default` rather than
    raising if it's missing or malformed -- a model's mistake shouldn't
    crash the turn.
    """
    lines = answer.strip().splitlines()
    if lines and lines[-1].strip().lower().startswith("next_due_in:"):
        try:
            value = float(lines[-1].split(":", 1)[1].strip())
            return "\n".join(lines[:-1]).strip(), value
        except ValueError:
            pass
    return answer.strip(), default


def _build_npc_decision_prompt(registrar: Registrar, alias: str) -> str:
    """Assemble an NPC's decision prompt from its agenda and what it has perceived."""
    agenda_df = core.safe_view(registrar, "agenda.value")
    agenda_text = ""
    alias_id = registrar.get_entity_id(alias)
    if agenda_df is not None and alias_id is not None:
        match = agenda_df[agenda_df["entity_id"] == alias_id]
        if not match.empty:
            agenda_text = match.iloc[-1]["agenda.value"]

    active = spatial.active_aliases(registrar) - {alias}
    memory = spatial.memory_aliases(registrar, alias) - {alias}
    remembered_only = sorted(memory - active)
    details = spatial.entity_descriptions(registrar, active | memory)

    parts = []
    if agenda_text:
        parts.append(f"Your agenda: {agenda_text}")
    if active:
        parts.append(f"Entities nearby right now: {', '.join(sorted(active))}")
    if remembered_only:
        parts.append(f"Entities you remember but can't currently perceive: {', '.join(remembered_only)}")
    if details:
        parts.append(f"What you know about them:\n{details}")
    parts.append(
        "What do you do this turn? Respond in first person, one or two "
        "sentences, exactly as if you were typing your action as a command."
    )
    return "\n".join(parts)


def update_data(registrar: Registrar, save_dir: Path, yaml_string: str, ctx: Context) -> None:
    """Update data box: merge+export, reusing the existing write path exactly."""
    _update_registry_and_sync(registrar, save_dir, yaml_string, ctx)


async def get_character_input(
    registrar: Registrar, alias: str, scene: str, replay: TurnReplay
) -> str:
    """Get character input box.

    NPC path prefers subagent (nobody real is behind an NPC) but falls
    back to responder="host" if it fails, e.g. no subagent key configured
    (see `TurnReplay.resolve_preferring_subagent`). Player-voiced path
    always needs a human (responder="human") -- only the actual human's
    message can answer this.
    """
    if spatial.character_interaction_type(registrar, alias) == "npc":
        decision_prompt = _build_npc_decision_prompt(registrar, alias)
        request = JudgmentRequest(prompt=decision_prompt)
        return await replay.resolve_preferring_subagent(request, _npc_spec)

    request = JudgmentRequest(prompt=f"It's {alias}'s turn.\n\n{scene}\n\nWhat do they do?")
    return await replay.resolve(request, responder="human")


async def resolve_event(
    registrar: Registrar, save_dir: Path, alias: str, action_text: str, replay: TurnReplay, ctx: Context
) -> tuple[str, float]:
    """Resolve event box: work out what happens, and how long it took.

    Returns (narration, next_due_in) -- process_event schedules `alias`
    with the latter via predict_event/push_event, uniformly for both paths.

    NPC path resolves via the existing resolver tool loop (its own nested
    generate_terrain/resolve_physics/update_data calls), responder="subagent",
    `replay` never touched. Player-voiced path always needs a human
    (responder="human"): the outcome has to be resolved against state as
    of right now, and only the outer conversation should narrate to a
    human (see CLAUDE.md). update_data is *not* called here for the
    player-voiced path -- the connected agent already has direct access
    to the plain `update_registry` tool and calls it itself; only the NPC
    path needs update_data threaded through its own resolver loop.
    """
    if spatial.character_interaction_type(registrar, alias) == "npc":
        # Captured from update_data's own next_due_in argument -- a typed
        # tool parameter, more robust than the player path's text-line
        # convention (see _NEXT_DUE_IN_INSTRUCTION).
        captured: dict[str, float] = {}

        async def dispatch(name: str, arguments: dict) -> str:
            try:
                if name == "generate_terrain":
                    return _terrain_agent.generate(arguments["description"])
                if name == "resolve_physics":
                    return _physics_agent.resolve(arguments["scenario"])
                if name == "update_data":
                    update_data(registrar, save_dir, arguments["yaml_string"], ctx)
                    captured["next_due_in"] = float(arguments["next_due_in"])
                    return "Merged into the registry."
                return f"Error: unknown tool {name!r}"
            except Exception as e:
                return f"Error: {e}"

        resolver_prompt = f"{alias}'s action: {action_text}"
        summary = await run_tool_loop(
            _npc_resolver_spec,
            [{"role": "user", "content": resolver_prompt}],
            _NPC_RESOLVER_TOOLS,
            dispatch,
            max_turns=MAX_NPC_TURN_TOOL_TURNS,
            api_key=resolve_anthropic_api_key(),
        )
        return f"{alias}: {action_text}\n{summary}", captured.get("next_due_in", 1.0)

    request = JudgmentRequest(prompt=f"{alias} attempts: {action_text}\n\n{_NEXT_DUE_IN_INSTRUCTION}")
    answer = await replay.resolve(request, responder="human")
    return _parse_next_due_in(answer)


async def character_communication(
    registrar: Registrar, save_dir: Path, alias: str, replay: TurnReplay
) -> tuple[str, str]:
    """Character communication box: Select character -> Narrate to character -> Get
    character input. Returns (scene, action_text); process_event passes action_text
    into resolve_event.
    """
    alias = spatial.select_character(registrar, alias)
    scene = spatial.narrate_to_character(registrar, alias)
    action_text = await get_character_input(registrar, alias, scene, replay)
    return scene, action_text


async def process_event(
    registrar: Registrar, save_dir: Path, alias: str, replay: TurnReplay, ctx: Context
) -> str:
    """Process event box: Character communication -> Resolve event -> (Update data,
    NPC path only, see resolve_event) -> Predict event -> Push event -- this
    function is PROC's zoom-in target in the turn-flow diagram.
    """
    _scene, action_text = await character_communication(registrar, save_dir, alias, replay)
    narration, next_due_in = await resolve_event(registrar, save_dir, alias, action_text, replay, ctx)
    due_at = core.predict_event(registrar, alias, next_due_in)
    core.push_event(registrar, alias, due_at, time=_next_time_stamp(ctx))
    return narration


async def resolve_base_event(alias: str, replay: TurnReplay) -> tuple[str, float]:
    """Resolve a base-module event: what happens now that `alias` is due,
    and how long until it's next due -- inf (never again, see
    `core.pop_event`) if the answer omits `next_due_in`, unlike the
    character module's 1-second default.

    Always responder="host": no player is ever behind a base event, and
    there's no subagent persona to fall back from either -- see
    `TurnReplay.resolve_preferring_subagent` for the module that has one.
    """
    request = JudgmentRequest(prompt=f"{alias} is due.\n\n{_BASE_NEXT_DUE_IN_INSTRUCTION}")
    answer = await replay.resolve(request, responder="host")
    return _parse_next_due_in(answer, default=float("inf"))


async def process_base_event(registrar: Registrar, alias: str, replay: TurnReplay, ctx: Context) -> str:
    """Base module's process event box: Resolve event -> Predict event ->
    Push event -- no character-communication step first, unlike
    `process_event`: a base event has no agency to ask "what do you do" of,
    it just resolves.
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

    Branches once, up front, on whether the character module is active --
    `spatial.pop_event`/`process_event` (character-aware) when it is,
    `core.pop_event`/`process_base_event` (no notion of character) when
    it isn't. One loop either way: this is what makes `advance_simulation`
    a single tool rather than a character-ful one and a separate base one.

    `resume_alias`/`replay` re-enter that pair for a turn already in
    progress (decoded from `advance_simulation`'s `resume_token`) instead
    of popping fresh -- `replay`'s answers-so-far replay from cache (see
    `story_simulator.resolve.TurnReplay`), and if the newest call now
    completes, execution falls through into the ordinary loop for
    whatever's next.

    Returns (alias, replay, prompt, responder): `alias`/`replay`/`responder`
    are None only when the queue is empty; otherwise `alias`/`replay` are
    what `advance_simulation` encodes into a `resume_token`, and
    `responder` ("human" or "host") says who it's asking.
    """
    character_enabled = "character" in enabled_modules()

    async def _process(process_alias: str, process_replay: TurnReplay) -> str:
        if character_enabled:
            return await process_event(registrar, save_dir, process_alias, process_replay, ctx)
        return await process_base_event(registrar, process_alias, process_replay, ctx)

    if resume_alias is not None:
        assert replay is not None
        try:
            await _process(resume_alias, replay)
        except NeedsExternalInput as e:
            return resume_alias, replay, e.prompt, e.responder
        # No exception: this turn finished. Fall through to the ordinary
        # loop below rather than returning, since more entities may now be due.

    while True:
        alias = spatial.pop_event(registrar) if character_enabled else core.pop_event(registrar)
        if alias is None:
            return None, None, "Nothing scheduled.", None
        if not core.is_event_valid(registrar, alias):
            continue
        _current_world_time[ctx.request_context.session] = core.advance_clock(registrar, alias)
        replay = TurnReplay(answers=[])
        try:
            await _process(alias, replay)
        except NeedsExternalInput as e:
            return alias, replay, e.prompt, e.responder
        # No exception: this turn resolved fully -- loop back and pop
        # whatever's due next. A character turn usually completes here
        # without pausing (responder="subagent" succeeding), but can pause
        # like a player-voiced one on fallback to responder="host". A base
        # event always pauses unless this exact call was already answered
        # by a prior replay.


def _encode_token(alias: str, answers: list[str]) -> str:
    """Serialize a paused turn's resumption state into an opaque token.

    Self-contained, not a lookup key into server memory -- the host
    round-trips this same string back via `advance_simulation`'s own
    `resume_token` argument, so whichever subprocess decodes it (even a
    fresh one after a restart) can resume identically.
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

    With the character module enabled (on by default): the player-voiced
    character's action or resolution, or (if no subagent key is
    configured) an NPC's own decision. With it disabled: the base
    event-driven simulation -- every due entity resolves via
    responder="host", no character/NPC concept at all.

    Call with neither argument to start (or continue after a prior call
    finished with nothing left scheduled). That, and every later call,
    returns either ``{"status": "done", "narration": ...}`` or
    ``{"status": "input_required", "prompt": ..., "responder": ..., "resume_token": ...}``.
    On the latter, `responder` is "human" (relay `prompt` to the actual
    player and use their answer) or "host" (decide it yourself) -- then
    call again with that exact `resume_token` and your `answer`. No
    separate tool, and no server-side state to lose: `resume_token`
    carries everything needed to resume, surviving an MCP
    disconnect/reconnect between calls too.

    Args:
        resume_token: The `resume_token` from this session's last
            `input_required` result, or omitted to start/continue fresh.
        answer: The answer to that result's `prompt` (see `responder`).
            With the character module, the player's stated action, the
            resolved outcome of one, or an NPC's decision; with the base
            module, what happens (optionally ending with a
            `next_due_in: <seconds>` line -- omit it if there's nothing
            further to happen). Omit `answer` itself along with
            `resume_token` on a fresh call.
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
