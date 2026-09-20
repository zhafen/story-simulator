"""Tests for story_simulator.spatial -- position/distance/perception
primitives, generic over any entity, independent of whether it's a
character. Character-specific tests (memory, narrate_to_character,
character_in_event, decide_event) live in tests/test_character.py instead.
"""

import math

import pytest

from emc2p.mcp_server import SOURCE_KEY
from emc2p.registrar import Registrar

from story_simulator import game_config
from story_simulator.config import MANIFEST_DIR
from story_simulator.spatial import (
    active_aliases,
    entity_descriptions,
    entity_position,
    latest_positions,
    perceptible_entities,
    sync_active_tags,
    visibility_distance,
)

# Every test here drives a real Registrar through update()/load_manifest --
# the Hamilton driver construction that goes through dominates regardless
# of input size (see pyproject.toml's own `slow` marker docstring).
pytestmark = pytest.mark.slow


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={SOURCE_KEY: yaml_text})
    return registrar


_SAMPLE_WORLD_YAML = """
player:
    - character:
        interaction_type: player
    - position:
        x: 0.0
        y: 0.0

nearby_npc:
    - character:
        interaction_type: npc
    - position:
        x: 3.0
        y: 4.0

distant_rock:
    - object:
        type: rock
    - position:
        x: 500.0
        y: 0.0
"""


def test_entity_position_returns_known_position():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert entity_position(registrar, "nearby_npc") == (3.0, 4.0)


def test_entity_position_returns_none_for_unknown_alias():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert entity_position(registrar, "nonexistent") is None


def test_sync_active_tags_writes_active_component():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    sync_active_tags(registrar, {"nearby_npc"})
    assert active_aliases(registrar) == {"nearby_npc"}


def test_sync_active_tags_replaces_rather_than_unions():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    sync_active_tags(registrar, {"nearby_npc"})
    sync_active_tags(registrar, {"distant_rock"})
    assert active_aliases(registrar) == {"distant_rock"}


def test_entity_descriptions_returns_known_descriptions():
    registrar = _registrar_from_yaml(
        "thing:\n    - description:\n        value: A curious thing.\n"
        "    - position: {x: 0, y: 0}\n"
    )
    result = entity_descriptions(registrar, {"thing"})
    assert result == "thing: A curious thing."


def test_entity_descriptions_empty_for_no_aliases():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert entity_descriptions(registrar, set()) == ""


def test_entity_descriptions_includes_current_state():
    registrar = _registrar_from_yaml(
        "door:\n    - description: A plain door.\n    - state: open\n    - position: {x: 0, y: 0}\n"
    )
    result = entity_descriptions(registrar, {"door"})
    assert result == "door: A plain door. (state: open)"


_SIZED_WORLD_YAML = """
observer:
    - character:
        interaction_type: player
    - position:
        x: 0.0
        y: 0.0

nearby_tiny_coin:
    - object:
        type: coin
    - position:
        x: 1.0
        y: 0.0
    - size:
        value: 0.02

distant_tiny_coin:
    - object:
        type: coin
    - position:
        x: 5.0
        y: 0.0
    - size:
        value: 0.02

door_sized:
    - object:
        type: door
    - position:
        x: 150.0
        y: 0.0
    - size:
        value: 2.0

far_door_sized:
    - object:
        type: door
    - position:
        x: 500.0
        y: 0.0
    - size:
        value: 2.0

distant_mountain:
    - object:
        type: mountain
    - position:
        x: 5000.0
        y: 0.0
    - size:
        value: 1000.0

no_size_far:
    - object:
        type: unknown
    - position:
        x: 500.0
        y: 0.0
"""


def test_visibility_distance_matches_fov_formula():
    threshold_angle = math.radians(game_config.FOV_DEGREES * game_config.PERCEPTIBLE_FOV_FRACTION)
    assert visibility_distance(2.0) == 2.0 / math.tan(threshold_angle)


def test_perceptible_entities_includes_object_well_beyond_the_old_flat_radius():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    # 150m away, far past an old flat 20m default -- but a 2m-sized object's
    # own visibility distance (~191m) still reaches it.
    assert "door_sized" in perceptible_entities(registrar, "observer")


def test_perceptible_entities_excludes_object_past_its_own_visibility_distance():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    assert "far_door_sized" not in perceptible_entities(registrar, "observer")


def test_perceptible_entities_includes_large_object_far_beyond_old_flat_radius():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    assert "distant_mountain" in perceptible_entities(registrar, "observer")


def test_perceptible_entities_includes_tiny_object_within_its_own_visibility_distance():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    assert "nearby_tiny_coin" in perceptible_entities(registrar, "observer")


def test_perceptible_entities_excludes_tiny_object_beyond_its_own_visibility_distance():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    assert "distant_tiny_coin" not in perceptible_entities(registrar, "observer")


def test_perceptible_entities_falls_back_to_default_size_when_missing():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    assert "no_size_far" not in perceptible_entities(registrar, "observer")


def test_latest_positions_resolves_to_highest_time():
    registrar = _registrar_from_yaml("player:\n    - position: {x: 0.0, y: 0.0}\n")
    registrar.update(yaml_strings={SOURCE_KEY: "player:\n    - position: {x: 5.0, y: 5.0}\n"}, time=2)
    latest = latest_positions(registrar)
    row = latest[latest["entity_id.display_alias"] == "player"].iloc[0]
    assert (float(row["position.x"]), float(row["position.y"])) == (5.0, 5.0)
