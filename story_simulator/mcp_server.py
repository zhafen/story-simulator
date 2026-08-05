"""MCP server exposing story-simulator's world-state and narrative tools.

story-simulator is *just* this server — there is no in-process agent loop
here. `start_simulation`/`submit_input` run an event-driven simulation
loop (modeled on Sedgewick & Wayne's event-driven simulation, one function
per step -- see `process_event`/`character_communication`/`resolve_event`
and `story_simulator.spatial`'s `pop_event`/`predict_event`/`push_event`)
that fast-forwards through any due NPCs entirely server-side, and pauses
only when the player-voiced character is due, handing control back to
whatever MCP-aware client is connected (a human's chat agent, an automated
harness, ...) — that client IS the narrator: it perceives what's going on
from the returned prompt, calls `generate_terrain`/`resolve_physics` when
it needs a specialist's judgment, narrates directly in its own replies,
and calls `submit_input` to hand back its decision (which itself records
it via `update_data`/`update_registry`) and resume the loop. `perceive`/
`view_registry`/`view_entity`/`update_registry` remain directly callable
too, for anything outside that loop. `advance_npc_turn` is a thin wrapper
over the same `process_event` used internally by the loop, forced onto one
named NPC, kept for direct single-NPC use outside a full simulation pass.

The three-tier judgment resolver behind all of this
(`story_simulator.resolve`: nested subagent / MCP sampling / true yield)
is what lets `character_communication`/`resolve_event` reach a real
decision from any nesting depth without every intervening function having
to be a generator — see that module's docstring.

Structurally mirrors `iacs/iacs/mcp_server.py`: a session-scoped `Registrar`
kept in a `weakref.WeakKeyDictionary` (so a session's world state is cleaned
up automatically once the session ends), plain `@server.tool()` functions,
`server.run(transport="stdio")`.
"""

from __future__ import annotations

__iacs__ = {"solution of": "story_simulator_mission.stateless_client"}

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

from story_simulator import spatial
from story_simulator.agents import AgentSpec, complete, run_tool_loop
from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    MANIFEST_DIR,
    WORLD_FILE_ID,
    registry_schema_name,
    registry_url,
    resolve_anthropic_api_key,
    resolve_database_dsn,
)
from story_simulator.resolve import JudgmentRequest, NeedsPlayerInput, TurnReplay
from story_simulator.specialists import PhysicsAgent, TerrainAgent

PROD_NPC_CONFIG_PATH = Path(__file__).parent / "npc.yaml"
PROD_NPC_RESOLVER_CONFIG_PATH = Path(__file__).parent / "npc_resolver.yaml"
MAX_NPC_TURN_TOOL_TURNS = 8
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
# (alias, answers-so-far) for whichever turn start_simulation/submit_input
# last paused on, per session. Losing this on a subprocess restart just
# means the in-flight turn's judgment calls get asked again from scratch --
# safe, not lossy, since pop_event/select_character/narrate_to_character
# are pure reads (see story_simulator.resolve's module docstring).
_pending_turns: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

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
                            "How much in-world time (same placeholder ordering scale as "
                            "position.turn) this action took."
                        ),
                    },
                },
                "required": ["yaml_string", "next_due_in"],
            },
        },
    },
]

# The player-voiced path only has one free-text answer channel (submit_input),
# unlike the NPC path's typed update_data(next_due_in=...) tool parameter --
# so a resolve_event yield asks for next_due_in as a trailing text line
# instead, parsed back out by _parse_next_due_in. Whoever resolves a turn
# still supplies next_due_in explicitly either way, player and NPC alike --
# no separate hardcoded interval for either path (see plan section 5).
_NEXT_DUE_IN_INSTRUCTION = (
    "End your answer with a line formatted exactly as `next_due_in: <seconds>` "
    "stating how much in-world time this action took."
)


def _get_registrar(ctx: Context) -> Registrar:
    """Return this session's open world Registrar, or raise a clear error if none is open."""
    session = ctx.request_context.session
    if session not in _registrars:
        raise ValueError("No world open for this session yet — call start_world first.")
    return _registrars[session]


def _get_save_dir(ctx: Context) -> Path:
    return _save_dirs[ctx.request_context.session]


def _next_turn_stamp() -> int:
    """A monotonically increasing stamp for `position.turn` and friends.

    There's no more global per-turn counter (no per-turn pipeline drives one
    anymore) — tool calls happen in whatever order the connected agent
    decides, so the wall clock, truncated to whole seconds to fit the
    schema's `int` field, replaces it as the "which write is newer" signal
    `Registry.view_current` needs to resolve accumulated position history.
    """
    return int(time.time())


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
        "run as an event-driven simulation (one character due at a time, scheduled by its "
        "own next_due) rather than a fixed per-turn loop.\n\n"
        "Call start_world once, at the beginning, to open or seed a save. Then call "
        "start_simulation: it fast-forwards through any due NPCs entirely on its own, and "
        "pauses the moment the player-voiced character is due, returning what they perceive "
        "and what's being asked of them.\n\n"
        "Decide what happens to whatever it's asking about -- call generate_terrain if the "
        "action reaches somewhere with no established terrain yet, or resolve_physics if the "
        "outcome isn't obvious (a fall, a jump, a thrown object, a collision, structural "
        "collapse) -- then call submit_input with your answer to resume the loop. It will "
        "keep asking (first for the player's action, then separately for how that action "
        "resolves -- state the outcome and end that second answer with a line formatted "
        "exactly as `next_due_in: <seconds>`) and fast-forwarding through NPCs again until "
        "either it needs you once more or the schedule empties. Narrate every outcome "
        "directly to the character, one or two sentences, addressing them directly. Stay "
        "fully in-world: never break character, mention tools, or use metaphors or similes — "
        "describe things directly and literally.\n\n"
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
        "the same way the loop's own NPC fast-forwarding does) — reach for start_simulation/"
        "submit_input as the default, and these when you need something outside that loop."
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
        df = spatial.safe_view(registrar, component_type)
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


def _update_registry_and_sync(registrar: Registrar, save_dir: Path, yaml_string: str) -> None:
    """Merge `yaml_string` into the registry, then sync `save_dir`'s YAML to match."""
    registrar.update(
        input_dirs=[str(MANIFEST_DIR)],
        yaml_strings={WORLD_FILE_ID: yaml_string},
        time=_next_turn_stamp(),
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
    _update_registry_and_sync(registrar, save_dir, yaml_string)
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
    `memory`, the same way the old per-turn MapSystem did — just on demand
    instead of automatically every turn.
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
    raising if it's missing or malformed -- a model's mistake here
    shouldn't crash the turn, same reasoning as `run_tool_loop`'s own
    dispatch error handling.
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
    agenda_df = spatial.safe_view(registrar, "agenda.value")
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


def update_data(registrar: Registrar, save_dir: Path, yaml_string: str) -> None:
    """Update data box: merge+export, reusing the existing write path exactly."""
    _update_registry_and_sync(registrar, save_dir, yaml_string)


async def get_character_input(
    registrar: Registrar, alias: str, scene: str, replay: TurnReplay, ctx: Context
) -> str:
    """Get character input box.

    NPC path resolves fully server-side (tier 1 -- nobody real is behind
    an NPC) via the existing decide-step prompt/call. Player-voiced path
    yields (tier 3): only the actual human's actual message can answer
    this, so there's nothing to nest it in.
    """
    if spatial.character_interaction_type(registrar, alias) == "npc":
        decision_prompt = _build_npc_decision_prompt(registrar, alias)
        response = complete(
            _npc_spec, [{"role": "user", "content": decision_prompt}], api_key=resolve_anthropic_api_key()
        )
        return response.choices[0].message.content or ""

    request = JudgmentRequest(prompt=f"It's {alias}'s turn.\n\n{scene}\n\nWhat do they do?")
    return await replay.resolve(request, tier="yield")


async def resolve_event(
    registrar: Registrar, save_dir: Path, alias: str, action_text: str, replay: TurnReplay, ctx: Context
) -> tuple[str, float]:
    """Resolve event box: work out what happens, and how long it took.

    Returns (narration, next_due_in) -- process_event schedules `alias`
    with the latter via predict_event/push_event, uniformly for both paths.

    NPC path resolves via the existing resolver tool loop (its own nested
    generate_terrain/resolve_physics/update_data calls) -- tier 1, `replay`
    never touched, since nobody real is behind an NPC. Player-voiced path
    always yields (tier 3): the outcome can't be precomputed, since it has
    to be resolved against state as of right now, not whatever was true
    when this event was scheduled -- and only the outer conversation
    should narrate to a human (see CLAUDE.md). Update data, for the
    player-voiced path, is *not* called from here: the connected agent
    already has direct access to the plain `update_registry` tool and
    calls it itself the same way it always has, outside this replay
    mechanism entirely -- only the NPC path needs update_data threaded
    through its own resolver loop, since nothing else could call it there.
    """
    if spatial.character_interaction_type(registrar, alias) == "npc":
        # Captured from update_data's own next_due_in argument below -- a typed
        # tool parameter the model must fill in, more robust against a weak
        # model's mistakes than asking it to append a specific text line (the
        # player path's only option, see _NEXT_DUE_IN_INSTRUCTION below).
        captured: dict[str, float] = {}

        async def dispatch(name: str, arguments: dict) -> str:
            try:
                if name == "generate_terrain":
                    return _terrain_agent.generate(arguments["description"])
                if name == "resolve_physics":
                    return _physics_agent.resolve(arguments["scenario"])
                if name == "update_data":
                    update_data(registrar, save_dir, arguments["yaml_string"])
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
    answer = await replay.resolve(request, tier="yield")
    return _parse_next_due_in(answer)


async def character_communication(
    registrar: Registrar, save_dir: Path, alias: str, replay: TurnReplay, ctx: Context
) -> tuple[str, str]:
    """Character communication box: Select character -> Narrate to character -> Get
    character input. Returns (scene, action_text); process_event passes action_text
    into resolve_event.
    """
    alias = spatial.select_character(registrar, alias)
    scene = spatial.narrate_to_character(registrar, alias)
    action_text = await get_character_input(registrar, alias, scene, replay, ctx)
    return scene, action_text


async def process_event(
    registrar: Registrar, save_dir: Path, alias: str, replay: TurnReplay, ctx: Context
) -> str:
    """Process event box: Character communication -> Resolve event -> (Update data,
    NPC path only, see resolve_event) -> Predict event -> Push event -- this
    function is PROC's zoom-in target in the turn-flow diagram.
    """
    _scene, action_text = await character_communication(registrar, save_dir, alias, replay, ctx)
    narration, next_due_in = await resolve_event(registrar, save_dir, alias, action_text, replay, ctx)
    due_at = spatial.predict_event(registrar, alias, next_due_in)
    spatial.push_event(registrar, alias, due_at, turn=_next_turn_stamp())
    return narration


async def _run_event_loop(
    registrar: Registrar,
    save_dir: Path,
    ctx: Context,
    *,
    resume_alias: str | None = None,
    replay: TurnReplay | None = None,
) -> tuple[str | None, TurnReplay | None, str]:
    """The Event-driven simulation subgraph itself: Pop event -> Valid? -> Advance
    clock -> Process event, looping until either a NeedsPlayerInput pauses it
    (returned to the caller, not raised further) or the queue empties.

    `resume_alias`/`replay` re-enter `process_event` for a specific turn
    already in progress (what `submit_input` is resuming) instead of
    popping fresh -- `replay`'s answers-so-far mean everything up to the
    newest still-unanswered judgment call replays from cache (see
    `story_simulator.resolve.TurnReplay`), and if that call now completes,
    execution falls straight through into the ordinary loop below for
    whatever's next, rather than returning immediately.

    Returns (alias, replay, prompt): `alias`/`replay` are None only when
    the queue is empty (nothing left to stash); otherwise they're exactly
    what a follow-up `submit_input` needs to resume this same pause point.
    """
    if resume_alias is not None:
        assert replay is not None
        try:
            await process_event(registrar, save_dir, resume_alias, replay, ctx)
        except NeedsPlayerInput as e:
            return resume_alias, replay, e.prompt
        # No exception: this turn finished. Fall through to the ordinary
        # loop below rather than returning, since more entities (NPC or
        # player-voiced) may now be due.

    while True:
        alias = spatial.pop_event(registrar)
        if alias is None:
            return None, None, "Nothing scheduled."
        if not spatial.is_event_valid(registrar, alias):
            continue
        spatial.advance_clock(registrar, alias)
        replay = TurnReplay(answers=[])
        try:
            await process_event(registrar, save_dir, alias, replay, ctx)
        except NeedsPlayerInput as e:
            return alias, replay, e.prompt
        # NPC turn completed synchronously (tier 1, never yields) -- loop
        # back and pop whatever's due next.


@server.tool()
async def start_simulation(ctx: Context) -> str:
    """Start (or continue) the event loop: fast-forward through any due NPCs, and
    pause the moment the player-voiced character is due, returning what they
    perceive and what's being asked of them. Call submit_input with their
    answer to continue.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.start_simulation"}
    registrar = _get_registrar(ctx)
    save_dir = _get_save_dir(ctx)
    alias, replay, prompt = await _run_event_loop(registrar, save_dir, ctx)
    if alias is not None:
        _pending_turns[ctx.request_context.session] = (alias, replay.answers)
    return prompt


@server.tool()
async def submit_input(answer: str, ctx: Context) -> str:
    """Answer whatever start_simulation (or a previous submit_input) last asked, and
    continue the event loop from there.

    Args:
        answer: The player's stated action, or the resolved outcome of one
            (whichever this session's last start_simulation/submit_input
            call was actually asking for) -- see that call's own returned
            prompt for which.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.submit_input"}
    session = ctx.request_context.session
    if session not in _pending_turns:
        raise ValueError("No pending turn for this session -- call start_simulation first.")
    registrar = _get_registrar(ctx)
    save_dir = _get_save_dir(ctx)
    alias, prior_answers = _pending_turns.pop(session)
    replay = TurnReplay(answers=[*prior_answers, answer])
    new_alias, new_replay, prompt = await _run_event_loop(
        registrar, save_dir, ctx, resume_alias=alias, replay=replay
    )
    if new_alias is not None:
        _pending_turns[session] = (new_alias, new_replay.answers)
    return prompt


def _build_npc_decision_prompt(registrar: Registrar, alias: str) -> str:
    """Assemble an NPC's decision prompt from its agenda and what it has perceived."""
    agenda_df = spatial.safe_view(registrar, "agenda.value")
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


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
