"""Permanent live regression for task #57: does a weak model reason
about event *arrival order* correctly.

Checked exactly via a dedicated race_placement component rather than
by matching substrings in freeform outcome text.

Grew out of a throwaway diagnostic that isolated arrival-order reasoning
from tests/test_human_validated.py::test_car_parking_core_sim's parking-spot
assignment (same underlying bug, different consequence): 3/3 isolated runs
reasoned about arrival order correctly, versus the full parking test's
persistent ~1/3 failure rate on the same reasoning -- evidence the
confusion is tied to conflating "driving" and "parking" into one turn, not
a standalone arrival-order failure. Kept permanently (not as a heuristic
text match, which produced a false positive during that diagnostic -- see
docs/manifest/history.yaml) so this specific reasoning step has its own
exact, unambiguous check going forward.

tests/data/scenarios/race/scenario.yaml reuses the exact same
start_time/duration facts as tests/data/scenarios/parking/scenario.yaml
(so the correct finishing order is identical: car_b end_time 1020, car_c
1080, car_a 1800) but drops the restaurant/parking-spot framing entirely
in favor of a three-car race -- nothing to reason about except finishing
order, recorded via each car's own `race_placement.value` (defined
inline in that same scenario.yaml, not manifest/builtins.yaml -- nothing
outside this test needs it).
"""

from pathlib import Path

import pytest

from test_human_validated.helpers import HeadlessSession, _event_states, _load_registrar
from emc2p.registrar import Registrar
from emc2p.testing.registry_checks import write_time
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent.parent
RACE_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "race"

# Deliberately one open-ended instruction, not one per event (see
# #61/docs/manifest/history.yaml). Checks the final result and order, not turn count.
_RUN_TO_DONE_RACE_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names) until its status is \"done\". For each event's resolve step, "
    "record via update_registry that event's own outcome and event_state (complete), AND "
    "that car's own race_placement -- its 1-indexed finishing position among all three cars "
    "(1 = first to finish), based on which cars' own trips have already finished by this "
    "point in time. Don't narrate anything back to me."
)


def _placement(registrar: Registrar, alias: str) -> int | None:
    """The current `race_placement.value` recorded for an aliased car, or
    None if it has none yet."""
    df = safe_view_current(registrar, "race_placement.value", aliases=alias)
    if df is None or df.empty:
        return None
    return int(df.iloc[-1]["race_placement.value"])


@pytest.mark.live
def test_race_placement_recorded_in_order(tmp_path):
    """Each car's event.start_time/duration already *is* its own true
    finish time.

    pop_event's own mechanical sort (soonest end_time first) pops them
    in the real finishing order (B, C, A), not start order or trip
    length -- so by the time any one event resolves, whichever cars
    finished earlier are genuinely already finished, not a guess about
    entities that haven't been touched yet.

    Deliberately checks only the *final* result, not turn-by-turn state
    (see #61/docs/manifest/history.yaml: project_history.
    live_tests_decoupled_from_turn_count) -- the model runs the whole
    batch in one open-ended instruction, in as many or as few
    advance_simulation round-trips as it wants. What matters is (1) each
    car's final race_placement and (2) that the *order* was actually
    respected, not the turn count. Order evidence comes from each car's
    race_placement write being time-stamped with its own trip event's
    end_time (world time -- see core._next_time_stamp), confirming each
    placement was recorded while that car's own event resolved, not
    retroactively or out of turn.
    """
    save_dir = tmp_path / "test_save"

    # This test's whole point is the *connected* model's own arrival-order
    # reasoning -- explicit override of the keyed_subagent default.
    with HeadlessSession(save_dir, responder="host") as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={RACE_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_RACE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _placement(r, "car_b") == 1, (
            "Car B should be first to actually finish (it left earlier than Car C by more "
            f"than their trip-length difference) -- narration: {narration!r}"
        )
        assert _placement(r, "car_c") == 2, (
            "Car C should be second to finish (after Car B, before Car A) -- "
            f"narration: {narration!r}"
        )
        assert _placement(r, "car_a") == 3, (
            "Car A starts first but has the longest trip, so it should actually finish last "
            f"-- narration: {narration!r}"
        )

        states = _event_states(r)
        assert states.get("car_b_trip") == "complete", states
        assert states.get("car_c_trip") == "complete", states
        assert states.get("car_a_trip") == "complete", states

        times = {alias: write_time(r, "race_placement", alias) for alias in ("car_b", "car_c", "car_a")}
        assert times["car_b"] == pytest.approx(1020), (
            f"car_b's race_placement should be recorded at car_b_trip's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_c"] == pytest.approx(1080), (
            f"car_c's race_placement should be recorded at car_c_trip's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_a"] == pytest.approx(1800), (
            f"car_a's race_placement should be recorded at car_a_trip's own end_time -- {times}, narration: {narration!r}"
        )
