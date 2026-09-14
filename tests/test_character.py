"""Tests for story_simulator.character -- everything dependent on being a
character: memory, narrating to one, the character-event predicate
process_event uses, and character_interaction_type.

decide_event itself is exercised end-to-end via tests/test_character_event.py
(through advance_simulation), not directly here.
"""

import pytest

from emc2p.mcp_server import SOURCE_KEY
from emc2p.registrar import Registrar

from story_simulator.character import (
    character_in_event,
    character_interaction_type,
    is_character_event,
    memory_aliases,
    narrate_to_character,
    record_memory,
)
from story_simulator.config import MANIFEST_DIR
from story_simulator.spatial import active_aliases, sync_active_tags

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


def test_narrate_to_character_tags_active_and_records_memory():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    narration = narrate_to_character(registrar, "player")
    assert "nearby_npc" in narration
    assert active_aliases(registrar) == {"nearby_npc"}
    assert memory_aliases(registrar, "player") == {"nearby_npc"}


def test_narrate_to_character_reports_nothing_perceptible():
    registrar = _registrar_from_yaml("loner:\n    - character:\n        interaction_type: player\n    - position: {x: 0, y: 0}\n")
    assert narrate_to_character(registrar, "loner") == "Nothing else is within perceptible range of loner."


def test_character_in_event_finds_the_involved_character():
    registrar = _registrar_from_yaml(
        "player:\n"
        "    - character:\n"
        "        interaction_type: player\n"
        "talk_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 1.0\n"
        "    - involved_entity:\n"
        "        value: player\n"
    )
    assert character_in_event(registrar, "talk_event") == "player"
    assert is_character_event(registrar, "talk_event") is True


def test_character_in_event_none_for_a_base_event():
    registrar = _registrar_from_yaml(
        "gizmo_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 1.0\n"
    )
    assert character_in_event(registrar, "gizmo_event") is None
    assert is_character_event(registrar, "gizmo_event") is False


def test_character_in_event_none_when_involved_entity_is_not_a_character():
    registrar = _registrar_from_yaml(
        "rock:\n"
        "    - object:\n"
        "        type: rock\n"
        "rock_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 1.0\n"
        "    - involved_entity:\n"
        "        value: rock\n"
    )
    assert character_in_event(registrar, "rock_event") is None


def test_character_interaction_type_reads_the_field():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert character_interaction_type(registrar, "player") == "player"
    assert character_interaction_type(registrar, "nearby_npc") == "npc"


def test_character_interaction_type_none_for_non_character():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    assert character_interaction_type(registrar, "distant_rock") is None
