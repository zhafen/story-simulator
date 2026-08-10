from unittest.mock import MagicMock

import pytest
from iacs.registrar import Registrar

from story_simulator.collision import resolve_collision
from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID
from story_simulator.game_config import DEFAULT_COEFFICIENT_OF_RESTITUTION
from story_simulator.interaction import resolve_interaction


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text})
    return registrar


def _read_latest(registrar: Registrar, component_type: str, alias: str) -> float:
    df = registrar.view_current([f"{component_type}.value"]).execute()
    entity_id = registrar.get_entity_id(alias)
    match = df[df["entity_id"] == entity_id]
    return float(match.iloc[-1][f"{component_type}.value"])


def _is_destroyed(registrar: Registrar, alias: str) -> bool:
    if "destroyed" not in registrar.registry.component_types:
        return False
    df = registrar.view("destroyed").execute()
    return alias in set(df["entity_id.alias"])


def _make_physics_agent(velocity_a=(3.0, 0.0, 0.0), velocity_b=(-2.0, 0.0, 0.0)):
    agent = MagicMock()
    agent.identify_interacting_pairs.return_value = [("rock", "window")]
    agent.estimate_collision_velocities.return_value = (velocity_a, velocity_b)
    return agent


_SURVIVING_PAIR_YAML = """
rock:
    - object:
        type: rock
    - mass:
        value: 2.0
    - kinetic_energy:
        value: 9.0
    - binding_energy:
        value: 100.0

window:
    - object:
        type: window
    - mass:
        value: 3.0
    - kinetic_energy:
        value: 6.0
    - binding_energy:
        value: 100.0
"""


def test_both_entities_survive_a_collision():
    registrar = _registrar_from_yaml(_SURVIVING_PAIR_YAML)
    agent = _make_physics_agent()

    result = resolve_interaction(registrar, agent, ["rock", "window"], "a rock hits a window", time=1.0)

    assert "collide" in result
    agent.estimate_quantity.assert_not_called()
    assert not _is_destroyed(registrar, "rock")
    assert not _is_destroyed(registrar, "window")

    expected = resolve_collision(2.0, (3.0, 0.0, 0.0), 3.0, (-2.0, 0.0, 0.0), DEFAULT_COEFFICIENT_OF_RESTITUTION)
    assert _read_latest(registrar, "binding_energy", "rock") == pytest.approx(100.0 - expected.energy_lost / 2)
    assert _read_latest(registrar, "binding_energy", "window") == pytest.approx(100.0 - expected.energy_lost / 2)
    assert _read_latest(registrar, "kinetic_energy", "rock") == pytest.approx(_ke(2.0, expected.velocity_a_after))
    assert _read_latest(registrar, "kinetic_energy", "window") == pytest.approx(_ke(3.0, expected.velocity_b_after))


def _ke(mass, velocity):
    return 0.5 * mass * sum(v * v for v in velocity)


_ONE_DESTROYED_YAML = """
rock:
    - object:
        type: rock
    - mass:
        value: 2.0
    - kinetic_energy:
        value: 9.0
    - binding_energy:
        value: 100.0

window:
    - object:
        type: window
    - mass:
        value: 3.0
    - kinetic_energy:
        value: 6.0
    - binding_energy:
        value: 10.0
"""


def test_one_entity_destroyed_survivor_carries_leftover_energy():
    registrar = _registrar_from_yaml(_ONE_DESTROYED_YAML)
    agent = _make_physics_agent()

    result = resolve_interaction(registrar, agent, ["rock", "window"], "a rock hits a window", time=1.0)

    assert "window" in result and "destroyed" in result
    assert _is_destroyed(registrar, "window")
    assert not _is_destroyed(registrar, "rock")
    # total_energy (15) - window's binding energy (10) = 5 J left for rock.
    assert _read_latest(registrar, "kinetic_energy", "rock") == pytest.approx(5.0)
    # The collision-math branch never runs, so rock's binding energy is untouched.
    assert _read_latest(registrar, "binding_energy", "rock") == pytest.approx(100.0)
    agent.estimate_collision_velocities.assert_not_called()


_BOTH_DESTROYED_YAML = """
rock:
    - object:
        type: rock
    - mass:
        value: 2.0
    - kinetic_energy:
        value: 9.0
    - binding_energy:
        value: 10.0

window:
    - object:
        type: window
    - mass:
        value: 3.0
    - kinetic_energy:
        value: 6.0
    - binding_energy:
        value: 10.0
"""


def test_both_entities_destroyed_when_energy_exceeds_both_binding_energies():
    registrar = _registrar_from_yaml(_BOTH_DESTROYED_YAML)
    agent = _make_physics_agent()

    result = resolve_interaction(registrar, agent, ["rock", "window"], "a rock hits a window", time=1.0)

    assert "both destroyed" in result
    assert _is_destroyed(registrar, "rock")
    assert _is_destroyed(registrar, "window")
    agent.estimate_collision_velocities.assert_not_called()


_PERSISTENCE_YAML = """
rock:
    - object:
        type: rock
    - mass:
        value: 2.0
    - kinetic_energy:
        value: 9.0
    - binding_energy:
        value: 20.0

window:
    - object:
        type: window
    - mass:
        value: 3.0
    - kinetic_energy:
        value: 6.0
    - binding_energy:
        value: 20.0
"""


def test_binding_energy_persists_and_erodes_across_two_calls():
    """The second call must read the *reduced* binding energy from the first, not re-estimate it."""
    registrar = _registrar_from_yaml(_PERSISTENCE_YAML)
    agent = _make_physics_agent()

    resolve_interaction(registrar, agent, ["rock", "window"], "a rock hits a window", time=1.0)
    resolve_interaction(registrar, agent, ["rock", "window"], "a rock hits a window again", time=2.0)

    agent.estimate_quantity.assert_not_called()

    energy_lost_per_collision = resolve_collision(
        2.0, (3.0, 0.0, 0.0), 3.0, (-2.0, 0.0, 0.0), DEFAULT_COEFFICIENT_OF_RESTITUTION
    ).energy_lost

    # If the second call had re-estimated (or otherwise reset) binding energy
    # instead of reading the first call's reduced value, the total erosion
    # after two calls would equal one call's worth, not two.
    expected_final_binding_energy = 20.0 - energy_lost_per_collision
    assert _read_latest(registrar, "binding_energy", "rock") == pytest.approx(expected_final_binding_energy)
    assert _read_latest(registrar, "binding_energy", "window") == pytest.approx(expected_final_binding_energy)
