"""Single-call specialist agents backing the `generate_terrain`/`resolve_physics` MCP tools.

`TerrainAgent`/`PhysicsAgent` hold no state beyond their own `AgentSpec` and
make one plain, tool-free completion call per invocation — there's no
per-turn scheduling here, they only ever run when a connected agent (or
`advance_npc_turn`'s own nested loop) actually calls the corresponding tool.
"""

from __future__ import annotations

from pathlib import Path

from story_simulator.agents import AgentSpec, complete
from story_simulator.config import resolve_anthropic_api_key

PROD_TERRAIN_CONFIG_PATH = Path(__file__).parent / "terrain.yaml"
PROD_PHYSICS_CONFIG_PATH = Path(__file__).parent / "physics.yaml"


class TerrainAgent:
    """Invents terrain/environment details for a location, on request."""

    def __init__(self, config_path: Path = PROD_TERRAIN_CONFIG_PATH):
        self.spec = AgentSpec.from_yaml(config_path)

    def generate(self, description: str) -> str:
        """Return generated terrain/environment text for the given location `description`."""
        # A single, tool-free completion call: no prior turns to carry, no
        # follow-up tool use, just "here's what's known, describe the terrain."
        response = complete(
            self.spec,
            [{"role": "user", "content": description}],
            api_key=resolve_anthropic_api_key(),
        )
        return response.choices[0].message.content or ""


class PhysicsAgent:
    """Works out the plausible physical outcome of a described action, on request."""

    def __init__(self, config_path: Path = PROD_PHYSICS_CONFIG_PATH):
        self.spec = AgentSpec.from_yaml(config_path)

    def resolve(self, scenario: str) -> str:
        """Return a plausibility/outcome judgment for the given `scenario` text."""
        # Same shape as TerrainAgent.generate: one plain completion call,
        # no tools, no multi-turn back-and-forth.
        response = complete(
            self.spec,
            [{"role": "user", "content": scenario}],
            api_key=resolve_anthropic_api_key(),
        )
        return response.choices[0].message.content or ""
