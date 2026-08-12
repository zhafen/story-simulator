"""Tests for story_simulator.core -- the event-driven simulation kernel
that has to work with no optional module (character, npc, physics,
terrain, spatial) active at all.
"""

from iacs.registrar import Registrar

from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID
from story_simulator.core import pop_event


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text})
    return registrar


def test_pop_event_returns_none_with_no_event_component():
    registrar = _registrar_from_yaml("thing:\n    - description: Just a thing.\n")
    assert pop_event(registrar) is None


def test_pop_event_finds_a_scheduled_event_with_no_event_state_row_yet():
    """event_state is optional for pop_event's own purposes -- an event
    with start_time/duration set is a candidate whether or not anything
    has recorded its lifecycle state yet."""
    registrar = _registrar_from_yaml(
        "gizmo_event:\n"
        "    - event:\n"
        "        start_time: 1.0\n"
        "        duration: 2.0\n"
    )
    assert pop_event(registrar) == "gizmo_event"


def test_pop_event_returns_soonest_end_time():
    """end_time is start_time + duration, not either alone -- the later-
    starting, shorter event here actually has the earlier end_time."""
    registrar = _registrar_from_yaml(
        "ball_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 5.0\n"
        "domino_event:\n"
        "    - event:\n"
        "        start_time: 2.0\n"
        "        duration: 1.0\n"
    )
    assert pop_event(registrar) == "domino_event"


def test_pop_event_excludes_events_missing_start_time_or_duration():
    """An event not yet fully scheduled (either field still null) isn't a
    candidate -- unlike the next_due mechanism this replaces, where an
    entity with no row at all simply wasn't a candidate, here the row
    exists (event_state may say "not started") but the timing is
    incomplete."""
    registrar = _registrar_from_yaml(
        "scheduled_event:\n"
        "    - event:\n"
        "        start_time: 100.0\n"
        "        duration: 1.0\n"
        "unscheduled_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "    - event_state:\n"
        "        value: not started\n"
    )
    assert pop_event(registrar) == "scheduled_event"


def test_pop_event_treats_complete_as_permanently_done():
    registrar = _registrar_from_yaml(
        "finished_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 0.0\n"
        "    - event_state:\n"
        "        value: complete\n"
    )
    assert pop_event(registrar) is None


def test_pop_event_treats_interrupted_as_permanently_done_too():
    registrar = _registrar_from_yaml(
        "cut_short_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 0.0\n"
        "    - event_state:\n"
        "        value: interrupted\n"
    )
    assert pop_event(registrar) is None


def test_pop_event_skips_a_terminal_event_in_favor_of_a_pending_one():
    registrar = _registrar_from_yaml(
        "finished_event:\n"
        "    - event:\n"
        "        start_time: 0.0\n"
        "        duration: 0.0\n"
        "    - event_state:\n"
        "        value: complete\n"
        "pending_event:\n"
        "    - event:\n"
        "        start_time: 1.0\n"
        "        duration: 0.0\n"
        "    - event_state:\n"
        "        value: planned\n"
    )
    assert pop_event(registrar) == "pending_event"
