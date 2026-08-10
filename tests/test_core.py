"""Tests for story_simulator.core -- the base event-driven simulation
kernel that has to work with no optional module (character, npc, physics,
terrain, spatial) active at all.
"""

from iacs.registrar import Registrar

from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID
from story_simulator.core import pop_event


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text})
    return registrar


def test_pop_event_returns_none_with_no_next_due_component():
    registrar = _registrar_from_yaml("thing:\n    - description: Just a thing.\n")
    assert pop_event(registrar) is None


def test_pop_event_ignores_characters_and_needs_no_character_component():
    """Unlike spatial.next_due_entity, core.pop_event has no notion of
    "character" -- it works in a world with none, and doesn't require one
    to be scheduled."""
    registrar = _registrar_from_yaml(
        "gizmo:\n"
        "    - next_due:\n"
        "        value: 3.0\n"
    )
    assert pop_event(registrar) == "gizmo"


def test_pop_event_returns_soonest_due():
    registrar = _registrar_from_yaml(
        "ball:\n"
        "    - next_due:\n"
        "        value: 5.0\n"
        "domino:\n"
        "    - next_due:\n"
        "        value: 2.0\n"
    )
    assert pop_event(registrar) == "domino"


def test_pop_event_excludes_unscheduled_entities():
    """No next_due row at all means not a candidate -- unlike
    spatial.next_due_entity, there's no "-inf, always goes first" default
    for a base-module entity."""
    registrar = _registrar_from_yaml(
        "scheduled_thing:\n"
        "    - next_due:\n"
        "        value: 100.0\n"
        "unscheduled_thing:\n"
        "    - description: Never been pushed onto the schedule.\n"
    )
    assert pop_event(registrar) == "scheduled_thing"


def test_pop_event_treats_inf_as_permanently_done():
    registrar = _registrar_from_yaml(
        "finished_thing:\n"
        "    - next_due:\n"
        "        value: .inf\n"
    )
    assert pop_event(registrar) is None


def test_pop_event_skips_inf_entity_in_favor_of_a_finite_one():
    registrar = _registrar_from_yaml(
        "finished_thing:\n"
        "    - next_due:\n"
        "        value: .inf\n"
        "pending_thing:\n"
        "    - next_due:\n"
        "        value: 1.0\n"
    )
    assert pop_event(registrar) == "pending_thing"
