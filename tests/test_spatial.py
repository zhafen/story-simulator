import math

from iacs.registrar import Registrar

from story_simulator import game_config
from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID
from story_simulator.spatial import (
    active_aliases,
    distance,
    entities_within,
    entity_descriptions,
    entity_position,
    latest_positions,
    memory_aliases,
    merge_yaml_string,
    perceptible_entities,
    record_memory,
    sync_active_tags,
    visibility_distance,
)


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text})
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


def test_distance_between_two_aliases():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert distance(registrar, "player", "nearby_npc") == 5.0


def test_distance_accepts_bare_points():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert distance(registrar, (0.0, 0.0), (3.0, 4.0)) == 5.0


def test_entities_within_includes_only_entities_in_radius():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert entities_within(registrar, "player", 10.0) == {"nearby_npc"}


def test_entities_within_excludes_the_center_itself():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    result = entities_within(registrar, "player", 1000.0)
    assert "player" not in result
    assert result == {"nearby_npc", "distant_rock"}


def test_entities_within_empty_when_nothing_in_range():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert entities_within(registrar, "player", 1.0) == set()


def test_sync_active_tags_writes_active_component():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    sync_active_tags(registrar, {"nearby_npc"})
    assert active_aliases(registrar) == {"nearby_npc"}


def test_sync_active_tags_replaces_rather_than_unions():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    sync_active_tags(registrar, {"nearby_npc"})
    sync_active_tags(registrar, {"distant_rock"})
    assert active_aliases(registrar) == {"distant_rock"}


def test_record_memory_persists_across_active_changes():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    record_memory(registrar, "player", {"nearby_npc"})
    sync_active_tags(registrar, set())
    assert memory_aliases(registrar, "player") == {"nearby_npc"}


def test_record_memory_accumulates_across_calls():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    record_memory(registrar, "player", {"nearby_npc"})
    record_memory(registrar, "player", {"distant_rock"})
    assert memory_aliases(registrar, "player") == {"nearby_npc", "distant_rock"}


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


def test_entity_descriptions_shows_only_current_description():
    registrar = _registrar_from_yaml("door:\n    - description: first\n    - position: {x: 0, y: 0}\n")
    merge_yaml_string(registrar, "door:\n    - description: second\n", time=2)
    result = entity_descriptions(registrar, {"door"})
    assert result == "door: second"


def test_entity_descriptions_includes_current_state():
    registrar = _registrar_from_yaml(
        "door:\n    - description: A plain door.\n    - state: open\n    - position: {x: 0, y: 0}\n"
    )
    result = entity_descriptions(registrar, {"door"})
    assert result == "door: A plain door. (state: open)"


def test_entity_descriptions_shows_only_current_state():
    registrar = _registrar_from_yaml("door:\n    - state: open\n    - position: {x: 0, y: 0}\n")
    merge_yaml_string(registrar, "door:\n    - state: closed\n", time=2)
    result = entity_descriptions(registrar, {"door"})
    assert result == "door: (state: closed)"


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
    # 150m away, far past the old flat 20m default -- but a 2m-sized object's
    # own visibility distance (~191m) still reaches it.
    assert "door_sized" in perceptible_entities(registrar, "observer")


def test_perceptible_entities_excludes_object_past_its_own_visibility_distance():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    # 500m away, past a 2m-sized object's ~191m visibility distance.
    assert "far_door_sized" not in perceptible_entities(registrar, "observer")


def test_perceptible_entities_includes_large_object_far_beyond_old_flat_radius():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    # 5000m away, but a 1000m-tall object's own visibility distance reaches
    # far past that.
    assert "distant_mountain" in perceptible_entities(registrar, "observer")


def test_perceptible_entities_includes_tiny_object_within_its_own_visibility_distance():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    # 1m away; a 0.02m object's own visibility distance (~1.9m) still
    # reaches it -- no artificial floor needed for something this close.
    assert "nearby_tiny_coin" in perceptible_entities(registrar, "observer")


def test_perceptible_entities_excludes_tiny_object_beyond_its_own_visibility_distance():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    # 5m away, past a 0.02m object's own ~1.9m visibility distance -- there
    # is no min_radius floor to rescue it.
    assert "distant_tiny_coin" not in perceptible_entities(registrar, "observer")


def test_perceptible_entities_falls_back_to_default_size_when_missing():
    registrar = _registrar_from_yaml(_SIZED_WORLD_YAML)
    # 500m away with no size component -- falls back to
    # game_config.DEFAULT_ENTITY_SIZE (2m), whose visibility distance
    # (~191m) doesn't reach that far.
    assert "no_size_far" not in perceptible_entities(registrar, "observer")


def test_latest_positions_resolves_to_highest_time():
    registrar = Registrar()
    merge_yaml_string(registrar, "player:\n    - position: {x: 0.0, y: 0.0}\n", time=1)
    merge_yaml_string(registrar, "player:\n    - position: {x: 5.0, y: 5.0}\n", time=2)
    latest = latest_positions(registrar)
    row = latest[latest["entity_id.alias"] == "player"].iloc[0]
    assert (float(row["position.x"]), float(row["position.y"])) == (5.0, 5.0)
