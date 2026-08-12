"""Permanent live regression for task #57: does a weak model reason about
event *arrival order* correctly, checked exactly via a dedicated
race_placement component rather than by matching substrings in freeform
outcome text.

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
order, recorded via each car's own `race_placement.place` (see
manifest/builtins.yaml).
"""

from pathlib import Path

import pytest

from test_human_validated import HeadlessSession, _event_states, _load_registrar
from iacs.registrar import Registrar
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent
RACE_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "race"

_RESOLVE_ONE_RACE_EVENT_INSTRUCTION = (
    "Call advance_simulation. Answer its first prompt (resolving the next event whose "
    "end_time has been reached) by recording, via update_registry, that event's own "
    "outcome and event_state (complete), AND that car's own race_placement -- its "
    "1-indexed finishing position among all three cars (1 = first to finish), based on "
    "which cars' own trips have already finished by this point in time. Decide the full "
    "outcome now, in this one turn -- don't defer any part of it. Then answer its second "
    "prompt for that same event (planning any follow-up, or saying none is needed) -- two "
    "separate advance_simulation calls for the one event. Once both are answered, stop: do "
    "not call advance_simulation a third time. Don't narrate anything back to me."
)


def _placement(registrar: Registrar, alias: str) -> int | None:
    """The current `race_placement.place` recorded for an aliased car, or
    None if it has none yet."""
    df = safe_view_current(registrar, "race_placement.place", aliases=alias)
    if df is None or df.empty:
        return None
    return int(df.iloc[-1]["race_placement.place"])


@pytest.mark.live
def test_race_placement_recorded_in_order(tmp_path):
    """Each car's event.start_time/duration already *is* its own true
    finish time -- pop_event's own mechanical sort (soonest end_time
    first) pops them in the real finishing order (B, C, A), not start
    order or trip length -- so by the time any one event resolves,
    whichever cars finished earlier are genuinely already finished, not a
    guess about entities that haven't been touched yet. Checked turn by
    turn: after each event resolves, that car's own race_placement should
    be recorded exactly, and cars whose events haven't reached their own
    end_time yet should still show no placement at all.
    """
    save_dir = tmp_path / "test_save"

    with HeadlessSession(save_dir) as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={RACE_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RESOLVE_ONE_RACE_EVENT_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)
        assert _placement(r, "car_b") == 1, (
            "Car B should be first to actually finish (it left earlier than Car C by more "
            f"than their trip-length difference) -- narration: {narration!r}"
        )
        assert _placement(r, "car_c") is None and _placement(r, "car_a") is None, (
            "Only one event should have resolved this turn -- car_c's and car_a's own events "
            f"haven't reached their own end_time yet, so neither should have a recorded "
            f"placement -- narration: {narration!r}"
        )
        states = _event_states(r)
        assert states.get("car_b_trip") == "complete", states
        assert states.get("car_c_trip") != "complete" and states.get("car_a_trip") != "complete", states

        narration = session.send_turn(f"Again, {_RESOLVE_ONE_RACE_EVENT_INSTRUCTION}")
        r = _load_registrar(save_dir, narration)
        assert _placement(r, "car_c") == 2, (
            "Car C should be second to finish (after Car B, before Car A) -- "
            f"narration: {narration!r}"
        )
        assert _placement(r, "car_a") is None, (
            "Car A's own event still hasn't reached its own end_time yet, so it shouldn't "
            f"have a recorded placement -- narration: {narration!r}"
        )
        assert _placement(r, "car_b") == 1, (
            f"Car B's already-recorded placement shouldn't change -- narration: {narration!r}"
        )
        states = _event_states(r)
        assert states.get("car_c_trip") == "complete", states
        assert states.get("car_a_trip") != "complete", states

        narration = session.send_turn(
            "Call advance_simulation again and keep answering its prompts (resolve, then "
            "plan, for whatever event it names) until its status is \"done\" -- there's only "
            "one event left. Don't narrate anything back to me."
        )
        r = _load_registrar(save_dir, narration)
        assert _placement(r, "car_a") == 3, (
            "Car A starts first but has the longest trip, so it should actually finish last "
            f"-- narration: {narration!r}"
        )
        assert _placement(r, "car_b") == 1, (
            f"Car B's already-recorded placement shouldn't change -- narration: {narration!r}"
        )
        assert _placement(r, "car_c") == 2, (
            f"Car C's already-recorded placement shouldn't change -- narration: {narration!r}"
        )
