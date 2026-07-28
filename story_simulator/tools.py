"""Named, OpenAI-schema tool definitions shared across local agent tool loops.

Centralizing schemas here (rather than inlining them per-System, as
`ArchivistAgentSystem` used to) is what lets an `AgentSpec.tools` list of
plain names (e.g. `["view_registry", "update_registry", "iacs_mcp"]` in
`archivist.yaml`) resolve to real tool schemas without the System needing to
know the schema shape itself. The `"iacs_mcp"` sentinel is handled by
callers (it means "attach every tool the iacs MCP server exposes", resolved
at call time via `story_simulator.mcp_client.open_iacs_mcp_session`, since
those tools aren't known statically).

Each tool's *dispatch* logic is a plain, narrowly-scoped function rather
than a single uniform `(registrar, save_dir, turn, arguments)` signature —
`generate_terrain`/`resolve_physics` need a `TerrainAgent`/`PhysicsAgent`
instance, not registry access, so forcing one shared signature across all
four would mean padding every call with arguments most of them ignore.
Each `AgentSystem` still owns the actual `dispatch(name, arguments)` closure
`agents.run_tool_loop` calls, routing by name into whichever of these fits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from iacs.registrar import Registrar

from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID

if TYPE_CHECKING:
    from story_simulator.specialists import PhysicsAgent, TerrainAgent

IACS_MCP_SENTINEL = "iacs_mcp"

VIEW_REGISTRY_TOOL = {
    "type": "function",
    "function": {
        "name": "view_registry",
        "description": (
            "View all recorded data for one component type (e.g. \"position\", "
            "\"object\", \"character\") directly from the world registry — "
            "covers both the starting scenario and anything recorded in prior "
            "turns, so entities already known can be added to rather than "
            "duplicated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "component_type": {
                    "type": "string",
                    "description": "The component type to view, e.g. \"position\".",
                },
            },
            "required": ["component_type"],
        },
    },
}

UPDATE_REGISTRY_TOOL = {
    "type": "function",
    "function": {
        "name": "update_registry",
        "description": (
            "Merge entity-first YAML into the world registry, run through the "
            "same ETL pipeline used to load save files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "yaml_string": {
                    "type": "string",
                    "description": "Entity-first YAML content to merge in.",
                },
            },
            "required": ["yaml_string"],
        },
    },
}

GENERATE_TERRAIN_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_terrain",
        "description": (
            "Ask the Terrain specialist to invent environment/terrain details "
            "for a location the acting character has reached or can see, when "
            "nothing about that location is established yet. Returns "
            "descriptive text to narrate from, not something narrated directly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "What's already known about the location (position, "
                        "nearby entities, how the character got there) to "
                        "generate terrain consistent with."
                    ),
                },
            },
            "required": ["description"],
        },
    },
}

RESOLVE_PHYSICS_TOOL = {
    "type": "function",
    "function": {
        "name": "resolve_physics",
        "description": (
            "Ask the Physics specialist to work out the plausible outcome of "
            "an action with a physical result that isn't obvious (a fall, a "
            "jump, a collision, a thrown or dropped object, structural "
            "collapse, ...). Returns a plausibility judgment and outcome to "
            "narrate from, not something narrated directly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "description": (
                        "The attempted action and whatever entity state (sizes, "
                        "distances, positions) bears on whether/how it succeeds."
                    ),
                },
            },
            "required": ["scenario"],
        },
    },
}

TOOLS_BY_NAME = {
    "view_registry": VIEW_REGISTRY_TOOL,
    "update_registry": UPDATE_REGISTRY_TOOL,
    "generate_terrain": GENERATE_TERRAIN_TOOL,
    "resolve_physics": RESOLVE_PHYSICS_TOOL,
}


def resolve_tool_schemas(tool_names: list[str]) -> list[dict]:
    """Resolve an AgentSpec's `tools` names to schemas, skipping the `"iacs_mcp"` sentinel.

    Callers that support `"iacs_mcp"` (currently `ArchivistAgentSystem`) add
    the iacs MCP server's own tool schemas separately, since those aren't
    known until an MCP session is opened.
    """
    # Look each name up in the static registry, silently dropping the
    # sentinel — callers that care about it check for it separately.
    return [TOOLS_BY_NAME[name] for name in tool_names if name != IACS_MCP_SENTINEL]


def view_registry(registrar: Registrar, component_type: str) -> str:
    """Dispatch `view_registry`: a CSV dump of every recorded instance of `component_type`."""
    return registrar.view_df(component_type).to_csv()


def update_registry(registrar: Registrar, turn: int | None, yaml_string: str) -> str:
    """Dispatch `update_registry`: merge `yaml_string` into `registrar` and confirm.

    Mirrors `story_simulator.systems._merge_yaml_string`'s ETL call directly
    (rather than importing it) to keep this module free of a dependency on
    `story_simulator.systems`, which itself needs to import this module's
    schemas/functions.
    """
    # Run the model's YAML through the same ETL pipeline every other write
    # in this project uses, merging it straight into the live registrar.
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_string}, time=turn)
    # Confirmation text handed back to the model as the tool's result.
    return "Merged into the registry."


def generate_terrain(agent: "TerrainAgent", description: str) -> str:
    """Dispatch `generate_terrain`: delegate to the given `TerrainAgent` instance."""
    return agent.generate(description)


def resolve_physics(agent: "PhysicsAgent", scenario: str) -> str:
    """Dispatch `resolve_physics`: delegate to the given `PhysicsAgent` instance."""
    return agent.resolve(scenario)
