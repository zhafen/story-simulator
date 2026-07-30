"""MCP server exposing story-simulator's world-state and narrative tools.

story-simulator is *just* this server — there is no in-process agent loop
here. Whatever MCP-aware client connects (a human's chat agent, an
automated harness, ...) IS the narrator: it calls `perceive`/`view_registry`/
`view_entity` to see what's going on, calls `generate_terrain`/
`resolve_physics` when it needs a specialist's judgment, narrates directly
in its own replies, and calls `update_registry` to record what happened.
The one exception is `advance_npc_turn`, for a character nobody is chatting
to drive — it runs a small nested decide-narrate-record loop of its own
(itself calling `generate_terrain`/`resolve_physics`), since nothing else
will.

Structurally mirrors `iacs/iacs/mcp_server.py`: a session-scoped `Registrar`
kept in a `weakref.WeakKeyDictionary` (so a session's world state is cleaned
up automatically once the session ends), plain `@server.tool()` functions,
`server.run(transport="stdio")`.
"""

from __future__ import annotations

import asyncio
import shutil
import time
import weakref
from pathlib import Path

from iacs.registrar import Registrar
from mcp.server.fastmcp import Context, FastMCP

from story_simulator import spatial
from story_simulator.agents import AgentSpec, complete, run_tool_loop
from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    MANIFEST_DIR,
    WORLD_FILE_ID,
    resolve_anthropic_api_key,
)
from story_simulator.specialists import PhysicsAgent, TerrainAgent

REGISTRY_DB_FILENAME = "registry.duckdb"
PROD_NPC_CONFIG_PATH = Path(__file__).parent / "npc.yaml"
PROD_NPC_RESOLVER_CONFIG_PATH = Path(__file__).parent / "npc_resolver.yaml"
MAX_NPC_TURN_TOOL_TURNS = 8

_registrars: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_save_dirs: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

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
            "name": "update_registry",
            "description": "Merge entity-first YAML into the world registry.",
            "parameters": {
                "type": "object",
                "properties": {"yaml_string": {"type": "string"}},
                "required": ["yaml_string"],
            },
        },
    },
]


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


def _seed_save_dir(save_dir: Path, settings_dir: Path) -> None:
    """Copy a starting scenario's save data into a brand-new, still-empty save_dir."""
    if save_dir.resolve() == settings_dir.resolve():
        return
    if any(save_dir.iterdir()):
        return
    shutil.copytree(settings_dir, save_dir, dirs_exist_ok=True)


server = FastMCP(
    "story-simulator",
    instructions=(
        "You are the game master for a story-simulator world: a text simulation whose "
        "state lives in a structured entity/component registry, not just your own context.\n\n"
        "Call start_world once, at the beginning, to open or seed a save.\n\n"
        "For each player or NPC action you're narrating yourself:\n"
        "1. Call perceive for the acting character to see what's nearby (and record that "
        "they've perceived it).\n"
        "2. Decide what happens. Call generate_terrain if the action reaches somewhere with "
        "no established terrain yet, or resolve_physics if the outcome isn't obvious (a fall, "
        "a jump, a thrown object, a collision, structural collapse).\n"
        "3. Narrate the outcome directly to the character, in one or two sentences, addressing "
        "them directly. Stay fully in-world: never break character, mention tools, or use "
        "metaphors or similes — describe things directly and literally.\n"
        "4. Call update_registry with entity-first YAML recording what happened — new "
        "positions, new entities, changed details — reusing existing aliases (attach new data "
        "to an existing entity via a `same_as` component rather than creating a disconnected "
        "duplicate). If the action puts the character at the same place as an existing entity, "
        "use that entity's exact recorded coordinates rather than recomputing a new position "
        "from an approximate stated distance.\n\n"
        "Use view_registry/view_entity to look up what's already known before deciding — don't "
        "invent entities or details nothing has established.\n\n"
        "For an NPC nobody is directly chatting with, call advance_npc_turn instead of doing "
        "steps 1-4 yourself — it decides, narrates, and records that NPC's turn on its own."
    ),
)


@server.tool()
def start_world(save_dir: str, ctx: Context, settings_dir: str | None = None) -> str:
    """Open a world save for this session, seeding it from `settings_dir` if it's empty.

    Args:
        save_dir: Directory holding (or to hold) this world's save data.
        settings_dir: Starting scenario to seed a brand-new save_dir from
            (an EC directory, e.g. containing setting.yaml). Defaults to
            story-simulator's plain default world (a player, a door, an
            empty expanse). Ignored if save_dir already has any save data.
    """
    save_dir_path = Path(save_dir)
    settings_path = Path(settings_dir) if settings_dir else DEFAULT_WORLD_DIR
    save_dir_path.mkdir(parents=True, exist_ok=True)
    _seed_save_dir(save_dir_path, settings_path)

    registrar = Registrar.load(save_dir_path / REGISTRY_DB_FILENAME)
    # Only load the seed EC files into the registry the first time this
    # save_dir is ever opened (a brand-new duckdb has no component types
    # yet) — a resumed save's accumulated state already lives in the
    # persisted registry, so reloading the loose seed YAML again on every
    # start_world call would re-merge the same starting entities repeatedly.
    if not registrar.registry.component_types:
        found = sorted(
            f for pattern in ("*.yaml", "*.yml") for f in save_dir_path.rglob(pattern)
        )
        if found:
            registrar.update(input_dirs=[str(MANIFEST_DIR), *(str(f) for f in found)])

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
    registrar = _get_registrar(ctx)
    return registrar.view_df(component_type).to_csv()


@server.tool()
def view_entity(entity_id: str, ctx: Context) -> str:
    """Return every recorded component instance for a specific entity.

    Args:
        entity_id: Entity alias (e.g. "player" or "journaling_desk.desk").
    """
    registrar = _get_registrar(ctx)
    lines = []
    for component_type in sorted(registrar.registry.component_types):
        df = spatial.safe_view(registrar, component_type)
        if df is None or df.empty or "entity_id.alias" not in df.columns:
            continue
        matches = df[df["entity_id.alias"] == entity_id]
        for _, row in matches.iterrows():
            fields = {k: v for k, v in row.items() if k not in ("entity_id", "entity_id.alias")}
            lines.append(f"{component_type}: {fields}")
    if not lines:
        return f"No data found for {entity_id!r}."
    return f"# {entity_id}\n" + "\n".join(lines)


@server.tool()
def update_registry(yaml_string: str, ctx: Context) -> str:
    """Merge entity-first YAML into the world registry, run through the same ETL as save files.

    Args:
        yaml_string: Entity-first YAML content to merge in.
    """
    registrar = _get_registrar(ctx)
    registrar.update(
        input_dirs=[str(MANIFEST_DIR)],
        yaml_strings={WORLD_FILE_ID: yaml_string},
        time=_next_turn_stamp(),
    )
    return "Merged into the registry."


@server.tool()
def perceive(reference_alias: str, ctx: Context, radius: float = spatial.DEFAULT_PERCEPTION_RADIUS) -> str:
    """Return what `reference_alias` can currently perceive within `radius` meters, and record it.

    Tags each perceived entity `active` (replacing whatever was previously
    tagged active) and merges them into `reference_alias`'s permanent
    `memory`, the same way the old per-turn MapSystem did — just on demand
    instead of automatically every turn.
    """
    registrar = _get_registrar(ctx)
    nearby = spatial.entities_within(registrar, reference_alias, radius)
    spatial.sync_active_tags(registrar, nearby)
    spatial.record_memory(registrar, reference_alias, nearby)
    if not nearby:
        return f"Nothing else is within {radius} meters of {reference_alias}."
    details = spatial.entity_descriptions(registrar, nearby)
    parts = [f"Entities near {reference_alias}: {', '.join(sorted(nearby))}"]
    if details:
        parts.append(details)
    return "\n".join(parts)


@server.tool()
def generate_terrain(description: str) -> str:
    """Invent environment/terrain details for a location with nothing established yet.

    Args:
        description: What's already known about the location (position,
            nearby entities, how the character got there) to generate
            terrain consistent with.
    """
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
    return _physics_agent.resolve(scenario)


@server.tool()
def advance_npc_turn(npc_alias: str, ctx: Context) -> str:
    """Decide, narrate, and record one NPC's turn, since nobody is chatting to drive it directly.

    Args:
        npc_alias: The NPC's own alias (its `character.interaction_type`
            should be "npc").
    """
    registrar = _get_registrar(ctx)
    return asyncio.run(_advance_npc_turn_async(registrar, npc_alias))


async def _advance_npc_turn_async(registrar: Registrar, npc_alias: str) -> str:
    # Step 1: perceive — same effect as the perceive tool, called in-process.
    nearby = spatial.entities_within(registrar, npc_alias, spatial.DEFAULT_PERCEPTION_RADIUS)
    spatial.sync_active_tags(registrar, nearby)
    spatial.record_memory(registrar, npc_alias, nearby)

    # Step 2: decide — a single non-tool completion call, scoped to what
    # this NPC has actually perceived (active ∪ memory) plus its agenda.
    decision_prompt = _build_npc_decision_prompt(registrar, npc_alias)
    decision_response = complete(
        _npc_spec,
        [{"role": "user", "content": decision_prompt}],
        api_key=resolve_anthropic_api_key(),
    )
    command = decision_response.choices[0].message.content or ""

    # Step 3: narrate + record — a small tool-calling loop (its own nested
    # generate_terrain/resolve_physics/update_registry calls) since there's
    # no human/chat agent doing this on the NPC's behalf.
    async def dispatch(name: str, arguments: dict) -> str:
        try:
            if name == "generate_terrain":
                return _terrain_agent.generate(arguments["description"])
            if name == "resolve_physics":
                return _physics_agent.resolve(arguments["scenario"])
            if name == "update_registry":
                registrar.update(
                    input_dirs=[str(MANIFEST_DIR)],
                    yaml_strings={WORLD_FILE_ID: arguments["yaml_string"]},
                    time=_next_turn_stamp(),
                )
                return "Merged into the registry."
            return f"Error: unknown tool {name!r}"
        except Exception as e:
            return f"Error: {e}"

    resolver_prompt = f"{npc_alias}'s action: {command}"
    summary = await run_tool_loop(
        _npc_resolver_spec,
        [{"role": "user", "content": resolver_prompt}],
        _NPC_RESOLVER_TOOLS,
        dispatch,
        max_turns=MAX_NPC_TURN_TOOL_TURNS,
        api_key=resolve_anthropic_api_key(),
    )
    return f"{npc_alias}: {command}\n{summary}"


def _build_npc_decision_prompt(registrar: Registrar, alias: str) -> str:
    """Assemble an NPC's decision prompt from its agenda and what it has perceived."""
    agenda_df = spatial.safe_view(registrar, "agenda.value")
    agenda_text = ""
    if agenda_df is not None:
        match = agenda_df[agenda_df["entity_id.alias"] == alias]
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
