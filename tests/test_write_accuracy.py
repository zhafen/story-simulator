"""Live regressions checking the *write* stage in isolation -- given the
already-decided outcome directly (no arrival-order or driving/parking
reasoning required), does the model still call update_registry correctly:
right component type, right field, right value, on the right entity?

Complements tests/test_race_placement_live.py and
tests/test_parking_split_live.py, which require the model to both derive
the correct answer AND record it -- a failure there doesn't say which half
broke. These tests remove the reasoning half by handing the answer to the
model directly in the instruction, reusing the exact same scenario
fixtures (tests/data/scenarios/race, tests/data/scenarios/parking) so a
failure here isolates the write step itself, independent of whether the
model can also derive that answer on its own -- i.e. whether the model is
using the MCP tools appropriately given the right input, not whether it
can work out what the right input is.

Single rep per test, like the rest of this suite's live tests -- these are
permanent regression gates, not tests/location_write_harness.py's
comparative many-rep diagnostic (which already isolates the write step for
a single-car/single-spot case; these extend that same idea to the
multi-entity race_placement and parking scenarios the reasoning-focused
live tests use).
"""

from pathlib import Path

import pytest

from test_human_validated import HeadlessSession, _event_states, _load_registrar, _location, _parked_at
from emc2p.testing.registry_checks import unexpected_components
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent
PARKING_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking"
RACE_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "race"

# The scenario seed's own starting components (object, description) plus
# the one field a correct write is supposed to add to each car -- anything
# else showing up is a misattribution candidate (see
# emc2p.testing.registry_checks.unexpected_components).
_EXPECTED_LOCATION_COMPONENTS = {"object", "description", "location"}
_EXPECTED_RACE_PLACEMENT_COMPONENTS = {"object", "description", "race_placement"}

# Same first-come-first-served facts as test_parking_split_live.py's
# scenario, but handed to the model directly instead of left for it to
# derive from start_time/duration -- isolates whether it can still record
# three separate entities' locations correctly via update_registry once
# arrival-order reasoning is no longer part of the task.
_PARKING_WRITE_GIVEN_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names) until its status is \"done\". Each car's parking spot is "
    "already decided -- don't reason about arrival order, just record it: car_b parked in "
    "parking_spot_1, car_c parked in parking_spot_2, car_a parked on the street. For each "
    "event's resolve step, record via update_registry that event's own outcome and "
    "event_state (complete), AND that car's own final location using the assignment above. "
    "Don't narrate anything back to me."
)

# Same finishing order as test_race_placement_live.py's scenario, handed
# to the model directly instead of left for it to derive. Stated as plain
# integers (matching race_placement.value's own int schema, see
# tests/data/scenarios/race/scenario.yaml), not ordinal words ("1st") --
# confirmed live that ordinal phrasing here nudges the model into writing
# the ordinal string itself ("1st") instead of the int the schema wants,
# which would test the instruction's own wording, not the write step this
# test is meant to isolate.
_RACE_WRITE_GIVEN_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names) until its status is \"done\". Each car's finishing place is "
    "already decided -- don't reason about arrival order, just record it: car_b's "
    "race_placement is 1, car_c's race_placement is 2, car_a's race_placement is 3 (each an "
    "integer finishing position, 1 = first). For each event's resolve step, record via "
    "update_registry that event's own outcome and event_state (complete), AND that car's own "
    "race_placement using the assignment above. Don't narrate anything back to me."
)


def _placement(registrar, alias: str) -> int | str | None:
    """The current `race_placement.value` recorded for an aliased car, or
    None if it has none yet. Returns the raw recorded value uncoerced if
    it isn't int-like (e.g. a misfire that wrote "1st" instead of 1) so a
    failing assertion shows what was actually written instead of crashing
    on a bare `int()` conversion.
    """
    df = safe_view_current(registrar, "race_placement.value", aliases=alias)
    if df is None or df.empty:
        return None
    value = df.iloc[-1]["race_placement.value"]
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


@pytest.mark.live
def test_car_parking_write_accuracy_given_assignment(tmp_path):
    """Given each car's final parking spot directly, does update_registry
    end up with exactly that -- no misattributed component, no dropped
    write -- across all three cars and all three trip events?"""
    save_dir = tmp_path / "test_save"

    with HeadlessSession(save_dir) as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={PARKING_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_PARKING_WRITE_GIVEN_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _parked_at(_location(r, "car_b"), "parking_spot_1"), (
            f"car_b was told to park in parking_spot_1 -- narration: {narration!r}"
        )
        assert _parked_at(_location(r, "car_c"), "parking_spot_2"), (
            f"car_c was told to park in parking_spot_2 -- narration: {narration!r}"
        )
        assert _parked_at(_location(r, "car_a"), "street"), (
            f"car_a was told to park on the street -- narration: {narration!r}"
        )

        states = _event_states(r)
        for alias in ("car_a_trip", "car_b_trip", "car_c_trip"):
            assert states.get(alias) == "complete", states

        for alias in ("car_a", "car_b", "car_c"):
            misfires = unexpected_components(r, alias, _EXPECTED_LOCATION_COMPONENTS)
            assert not misfires, f"{alias} got unexpected components {misfires} -- narration: {narration!r}"


@pytest.mark.live
def test_race_placement_write_accuracy_given_assignment(tmp_path):
    """Given each car's finishing place directly, does update_registry end
    up with exactly that -- no misattributed component, no dropped write --
    across all three cars and all three trip events?"""
    save_dir = tmp_path / "test_save"

    with HeadlessSession(save_dir) as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={RACE_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RACE_WRITE_GIVEN_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _placement(r, "car_b") == 1, f"car_b was told it finished 1st -- narration: {narration!r}"
        assert _placement(r, "car_c") == 2, f"car_c was told it finished 2nd -- narration: {narration!r}"
        assert _placement(r, "car_a") == 3, f"car_a was told it finished 3rd -- narration: {narration!r}"

        states = _event_states(r)
        for alias in ("car_a_trip", "car_b_trip", "car_c_trip"):
            assert states.get(alias) == "complete", states

        for alias in ("car_a", "car_b", "car_c"):
            misfires = unexpected_components(r, alias, _EXPECTED_RACE_PLACEMENT_COMPONENTS)
            assert not misfires, f"{alias} got unexpected components {misfires} -- narration: {narration!r}"
