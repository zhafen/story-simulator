"""Single-call specialist agents backing the `generate_terrain`/`resolve_physics` MCP tools.

Hold no state beyond their own `AgentSpec`; one plain, tool-free
completion call per invocation, no per-turn scheduling.
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
        # Single, tool-free completion call: no prior turns, no follow-up.
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
        # Same shape as TerrainAgent.generate.
        response = complete(
            self.spec,
            [{"role": "user", "content": scenario}],
            api_key=resolve_anthropic_api_key(),
        )
        return response.choices[0].message.content or ""
