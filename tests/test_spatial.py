from iacs.registrar import Registrar

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
    record_memory,
    sync_active_tags,
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


def test_latest_positions_resolves_to_highest_turn():
    registrar = Registrar()
    merge_yaml_string(registrar, "player:\n    - position: {x: 0.0, y: 0.0}\n", turn=1)
    merge_yaml_string(registrar, "player:\n    - position: {x: 5.0, y: 5.0}\n", turn=2)
    latest = latest_positions(registrar)
    row = latest[latest["entity_id.alias"] == "player"].iloc[0]
    assert (float(row["position.x"]), float(row["position.y"])) == (5.0, 5.0)
