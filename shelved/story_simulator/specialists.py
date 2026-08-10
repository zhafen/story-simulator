"""Single-call specialist agents backing the `generate_terrain`/`resolve_physics` MCP tools.

Hold no state beyond their own `AgentSpec`; one plain, tool-free
completion call per invocation, no per-turn scheduling.

`PhysicsAgent`'s estimate_*/identify_interacting_pairs methods back
`resolve_interaction` (story_simulator/interaction.py) instead of
`resolve_physics`: same underlying agent/persona, but asked for one specific
number or pairing per call rather than a free-text plausibility judgment,
since `resolve_interaction`'s control flow (which pairs interact, in what
order, whether each survives) stays in plain Python -- these methods only
supply the individual fuzzy estimates that Python can't derive itself.
"""

from __future__ import annotations

import re
from pathlib import Path

from story_simulator.agents import AgentSpec, complete
from story_simulator.config import resolve_anthropic_api_key

PROD_TERRAIN_CONFIG_PATH = Path(__file__).parent / "terrain.yaml"
PROD_PHYSICS_CONFIG_PATH = Path(__file__).parent / "physics.yaml"

Vector3 = tuple[float, float, float]

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _parse_float(text: str) -> float:
    """Extract the first number in `text`.

    The Physics Resolver is asked to respond with only a number, but a
    model reply is still free text -- this tolerates stray whitespace or
    punctuation around the number rather than requiring an exact match.
    """
    match = _NUMBER_RE.search(text)
    if match is None:
        raise ValueError(f"No number found in Physics Resolver reply: {text!r}")
    return float(match.group())


def _parse_vector3(text: str) -> Vector3:
    """Extract the first three numbers in `text` as a velocity vector."""
    numbers = _NUMBER_RE.findall(text)
    if len(numbers) < 3:
        raise ValueError(f"Expected 3 numbers for a velocity vector, got: {text!r}")
    return (float(numbers[0]), float(numbers[1]), float(numbers[2]))


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

    def _ask(self, prompt: str) -> str:
        """Make one plain completion call and return its text -- the shape every method here shares."""
        response = complete(
            self.spec,
            [{"role": "user", "content": prompt}],
            api_key=resolve_anthropic_api_key(),
        )
        return response.choices[0].message.content or ""

    def resolve(self, scenario: str) -> str:
        """Return a plausibility/outcome judgment for the given `scenario` text."""
        return self._ask(scenario)

    def estimate_quantity(self, description: str, quantity_name: str, unit: str, scenario: str) -> float:
        """Estimate one numeric physical quantity for an entity, for `resolve_interaction`.

        Used for mass, kinetic energy, and binding energy alike -- only
        `quantity_name`/`unit` change between call sites.
        """
        prompt = (
            f"{scenario}\n\n"
            f"Estimate {description}'s {quantity_name} in {unit}. "
            "Respond with only the number, no units or other text."
        )
        return _parse_float(self._ask(prompt))

    def estimate_collision_velocities(
        self, description_a: str, description_b: str, scenario: str
    ) -> tuple[Vector3, Vector3]:
        """Estimate both entities' velocity vectors (m/s) in the collision's center-of-mass frame."""
        prompt = (
            f"{scenario}\n\n"
            f"In the center-of-mass frame of this collision, estimate the velocity vector "
            f"(vx, vy, vz, in m/s) of {description_a} and of {description_b} the instant they "
            "meet. Respond with exactly two lines, each three comma-separated numbers -- the "
            f"first line for {description_a}, the second for {description_b} -- and nothing else."
        )
        lines = [line for line in self._ask(prompt).strip().splitlines() if line.strip()]
        if len(lines) < 2:
            raise ValueError(f"Expected two velocity vectors from the Physics Resolver, got: {lines!r}")
        return _parse_vector3(lines[0]), _parse_vector3(lines[1])

    def identify_interacting_pairs(self, entity_ids: list[str], scenario: str) -> list[tuple[str, str]]:
        """Return which of `entity_ids` actually interact this turn, and in what order.

        Trivial for 0-2 entities (nothing to disambiguate); only asks the
        model when a genuine choice of pairs/order exists.
        """
        if len(entity_ids) < 2:
            return []
        if len(entity_ids) == 2:
            return [(entity_ids[0], entity_ids[1])]

        prompt = (
            f"{scenario}\n\n"
            f"Entities that might interact this turn: {', '.join(entity_ids)}.\n"
            "Which pairs of these actually interact, and in what order should each pair be "
            "resolved? Respond with exactly one pair per line, each line two of the given "
            "names separated by a comma, in resolution order. Omit any entity that doesn't "
            "interact with anything this turn. No other text."
        )
        pairs = []
        for line in self._ask(prompt).strip().splitlines():
            names = [name.strip() for name in line.split(",") if name.strip()]
            if len(names) == 2:
                pairs.append((names[0], names[1]))
        return pairs
