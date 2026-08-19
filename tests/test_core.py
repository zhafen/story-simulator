"""Tests for story_simulator.core -- the event-driven simulation kernel
that works with no optional module (character, npc, physics, terrain, spatial) active.
"""

import math

from emc2p.registrar import Registrar

from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID
from story_simulator.core import _update_registry_and_sync, pop_event, safe_view_current


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text})
    return registrar


def test_pop_event_returns_none_with_no_event_component():
    registrar = _registrar_from_yaml("thing:\n    - description: Just a thing.\n")
    assert pop_event(registrar) is None


def test_pop_event_finds_a_scheduled_event_with_no_event_state_row_yet():
    """event_state is optional for pop_event's own purposes -- an event with
    start_time/duration set is a candidate regardless of its lifecycle state."""
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
    candidate.

    Unlike the next_due mechanism this replaces, where an entity with no
    row at all simply wasn't a candidate -- here the row exists
    (event_state may say "not started") but the timing is incomplete.
    """
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


def test_update_registry_backfills_time_for_a_scenario_local_time_dimension_field(tmp_path):
    """A component type's own time_dimension field, declared only once (in
    the scenario's own seed YAML, not manifest/builtins.yaml), must still
    get backfilled on a *later* update_registry write that doesn't
    redeclare it -- mirroring race_placement.time in
    tests/data/scenarios/race/scenario.yaml, only ever loaded at
    start_world time, not by every later per-turn write.
    """
    save_dir = tmp_path / "test_save"
    registrar = Registrar()
    # Declares manifest/builtins.yaml's own schemas (component_type, field,
    # description, ...) -- the same call start_world makes before ever
    # merging a scenario's own seed YAML.
    registrar.update(input_dirs=[str(MANIFEST_DIR)])

    # Seed load: declares race_placement's own schema (time_dimension'd
    # "time" field), the same way start_world merges a scenario's seed YAML.
    _update_registry_and_sync(
        registrar,
        save_dir,
        "race_placement:\n"
        "    - component_type\n"
        "    - field:\n"
        "        value:\n"
        "            description: 1-indexed finishing position.\n"
        "            type: int\n"
        "        time:\n"
        "            description: World time this placement was recorded at.\n"
        "            type: float\n"
        "            nullable: true\n"
        "            time_dimension: true\n"
        "\n"
        "car_a:\n"
        "    - object:\n"
        "        type: car\n",
    )

    # A later, separate write -- like a real per-turn update_registry call --
    # that only writes race_placement's value, never redeclaring its schema.
    _update_registry_and_sync(registrar, save_dir, "car_a:\n    - race_placement:\n        value: 1\n")

    df = safe_view_current(registrar, "race_placement.time", aliases="car_a")
    assert df is not None and not df.empty
    assert not math.isnan(df.iloc[-1]["race_placement.time"])


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
