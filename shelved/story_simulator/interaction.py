"""Energy-based multi-entity interaction resolution, backing the `resolve_interaction` MCP tool.

Where `resolve_physics` (story_simulator/specialists.py's `PhysicsAgent.resolve`)
makes one free-text plausibility judgment about a single action, this module
resolves actual energy/momentum exchange between two or more entities the
Resolver has already identified as possibly interacting this turn --
plain Python drives the control flow (which pairs interact, in what order,
whether each one survives); the Physics Resolver is only asked for the
individual fuzzy estimates Python can't derive itself (an unknown mass,
kinetic energy, or binding energy; a pair's post-collision velocity
vectors).

Binding energy is the one persisted quantity that's never re-estimated once
established: every collision an entity survives erodes it by half the
kinetic energy the impact dissipated (see `_resolve_pair`), the same way
`position` accumulates a world-time-stamped history that `Registry.view_current`
resolves to "whatever's most recent." An object can survive many small
impacts and still eventually be destroyed by one it would once have
shrugged off. (Today `resolve_interaction` only ever reduces it -- a future
mechanism, e.g. repairs, may raise it back up, so don't assume it's
monotonic when reading it elsewhere.)

Known follow-up, out of scope here: entities tagged `destroyed` aren't yet
filtered out of `spatial.perceptible_entities`/`entities_within`, so a
destroyed object still shows up as perceivable until that's addressed
separately.
"""

from __future__ import annotations

import yaml
from iacs.registrar import Registrar

from story_simulator import spatial
from story_simulator.collision import kinetic_energy as _velocity_kinetic_energy, resolve_collision
from story_simulator.game_config import DEFAULT_COEFFICIENT_OF_RESTITUTION
from story_simulator.specialists import PhysicsAgent


def _destroyed_update(alias: str) -> dict:
    return {f"{alias}_destroyed_update": [{"same_as": {"value": alias}}, "destroyed"]}


def _get_or_estimate(
    registrar: Registrar,
    physics_agent: PhysicsAgent,
    alias: str,
    component_type: str,
    quantity_name: str,
    unit: str,
    scenario: str,
    updates: dict,
    time: float | None,
) -> float:
    """Read `alias`'s current `component_type.value`, or have the Physics Resolver estimate it.

    Mass, kinetic energy, and binding energy are all "retrieve-or-estimate"
    quantities in exactly this shape. A freshly estimated value is queued
    into `updates` so it's persisted (and never re-estimated again); an
    already-known value is left alone rather than rewritten.
    """
    known = spatial.latest_value(registrar, component_type, alias)
    if known is not None:
        return known
    value = physics_agent.estimate_quantity(spatial.entity_label(registrar, alias), quantity_name, unit, scenario)
    updates.update(spatial.value_update(alias, component_type, value, time))
    return value


def _resolve_pair(
    registrar: Registrar,
    physics_agent: PhysicsAgent,
    a: str,
    b: str,
    kinetic_energy: dict[str, float],
    binding_energy: dict[str, float],
    mass: dict[str, float],
    scenario: str,
    time: float,
    restitution: float,
    updates: dict,
) -> tuple[str, set[str]]:
    """Resolve one ordered pair, mutating `kinetic_energy`/`binding_energy` and queuing registry writes.

    Returns the pair's narration line and the set of aliases (0, 1, or 2 of
    `{a, b}`) destroyed by it.
    """
    total_energy = kinetic_energy[a] + kinetic_energy[b]
    destroy_a = total_energy > binding_energy[a]
    destroy_b = total_energy > binding_energy[b]

    if destroy_a and destroy_b:
        updates.update(_destroyed_update(a))
        updates.update(_destroyed_update(b))
        return (
            f"{a} and {b} released {total_energy:.1f} J, exceeding both of their binding "
            f"energies ({binding_energy[a]:.1f} J / {binding_energy[b]:.1f} J): both destroyed.",
            {a, b},
        )

    if destroy_a or destroy_b:
        destroyed_alias, survivor = (a, b) if destroy_a else (b, a)
        leftover = total_energy - binding_energy[destroyed_alias]
        kinetic_energy[survivor] = leftover
        updates.update(_destroyed_update(destroyed_alias))
        updates.update(spatial.value_update(survivor, "kinetic_energy", leftover, time))
        return (
            f"{destroyed_alias} released {total_energy:.1f} J, exceeding its "
            f"{binding_energy[destroyed_alias]:.1f} J binding energy: destroyed. {survivor} "
            f"continues with {leftover:.1f} J of kinetic energy.",
            {destroyed_alias},
        )

    for alias in (a, b):
        if alias not in mass:
            mass[alias] = _get_or_estimate(
                registrar, physics_agent, alias, "mass", "mass", "kilograms", scenario, updates, None
            )

    velocity_a, velocity_b = physics_agent.estimate_collision_velocities(
        spatial.entity_label(registrar, a), spatial.entity_label(registrar, b), scenario
    )
    result = resolve_collision(mass[a], velocity_a, mass[b], velocity_b, restitution)

    kinetic_energy[a] = _velocity_kinetic_energy(mass[a], result.velocity_a_after)
    kinetic_energy[b] = _velocity_kinetic_energy(mass[b], result.velocity_b_after)
    binding_energy[a] -= result.energy_lost / 2
    binding_energy[b] -= result.energy_lost / 2

    updates.update(spatial.value_update(a, "kinetic_energy", kinetic_energy[a], time))
    updates.update(spatial.value_update(b, "kinetic_energy", kinetic_energy[b], time))
    updates.update(spatial.value_update(a, "binding_energy", binding_energy[a], time))
    updates.update(spatial.value_update(b, "binding_energy", binding_energy[b], time))

    return (
        f"{a} and {b} collide, losing {result.energy_lost:.1f} J to the impact; both survive "
        f"with reduced binding energy ({binding_energy[a]:.1f} J / {binding_energy[b]:.1f} J).",
        set(),
    )


def resolve_interaction(
    registrar: Registrar,
    physics_agent: PhysicsAgent,
    entity_ids: list[str],
    scenario: str,
    time: float,
    restitution: float = DEFAULT_COEFFICIENT_OF_RESTITUTION,
) -> str:
    """Work out the energy-based outcome of `entity_ids`' interactions this turn, and record it.

    For every entity in `entity_ids`: retrieve or estimate its kinetic
    energy and binding energy (steps 2-3). Identify which pairs actually
    interact and in what order (step 4). For each pair in order (steps
    5-8): if the pair's total energy exceeds either side's binding energy,
    destroy whichever side(s) it exceeds -- both, if it exceeds both --
    and let any survivor carry the leftover energy forward; otherwise
    estimate both objects' center-of-mass-frame velocities, run the exact
    collision math, and erode both sides' binding energy by half the
    kinetic energy the impact dissipated. Returns a short, literal,
    Python-templated summary per pair for the Resolver to narrate from --
    never shown to a player verbatim, same contract as `resolve_physics`.

    `time` is this session's current world time (seconds since world
    creation, see `mcp_server._next_time_stamp`) -- the same axis every
    other time_dimension'd write in this project stamps with, not a
    separate per-tool clock.
    """
    updates: dict = {}
    kinetic_energy = {
        alias: _get_or_estimate(
            registrar, physics_agent, alias, "kinetic_energy", "kinetic energy", "Joules", scenario, updates, time
        )
        for alias in entity_ids
    }
    binding_energy = {
        alias: _get_or_estimate(
            registrar, physics_agent, alias, "binding_energy", "binding energy", "Joules", scenario, updates, time
        )
        for alias in entity_ids
    }
    mass: dict[str, float] = {}

    pairs = physics_agent.identify_interacting_pairs(entity_ids, scenario)

    destroyed: set[str] = set()
    outcomes: list[str] = []
    for a, b in pairs:
        if a in destroyed or b in destroyed:
            continue
        line, newly_destroyed = _resolve_pair(
            registrar, physics_agent, a, b, kinetic_energy, binding_energy, mass, scenario, time, restitution, updates
        )
        destroyed |= newly_destroyed
        outcomes.append(line)

    if updates:
        spatial.merge_yaml_string(registrar, yaml.safe_dump(updates, sort_keys=False), time=time)

    if not outcomes:
        return f"No entities among {', '.join(entity_ids)} interact this turn."
    return "\n".join(outcomes)
