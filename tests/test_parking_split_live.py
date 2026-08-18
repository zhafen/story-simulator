"""Live regression for task #65, investigating #57: does first-come-first-served
parking still come out right once "driving" and "parking" are no longer
bundled into one event's resolution?

tests/test_human_validated.py::test_car_parking_core_sim and
tests/test_race_placement_live.py's evidence (see #61/docs/manifest/
history.yaml: project_history.live_tests_decoupled_from_turn_count) pointed
at the *combined* driving+parking decision -- not turn pacing, not
arrival-order reasoning in isolation -- as what's eliciting the confusion:
the race test (arrival order only, no parking-spot decision) passed 3/3
under the same one-shot pacing that made the parking test fail 0/3. This
test isolates the opposite half of that question: keep the full
parking-spot consequence, but structurally split each car's drive and its
parking decision into two separate, pre-planned events (see
tests/data/scenarios/parking_split/scenario.yaml) rather than removing the
consequence like the race test did.

Follows #61's convention: one open-ended "run to done" instruction, final
registry state checked, order evidence via each write's own recorded
world time (core._next_time_stamp) rather than turn-by-turn pacing.
"""

from pathlib import Path

import pytest

from test_human_validated import (
    HeadlessSession,
    _event_states,
    _load_registrar,
    _location,
    _parked_at,
)
from emc2p.testing.registry_checks import write_time

REPO_ROOT = Path(__file__).parent.parent
PARKING_SPLIT_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking_split"

_RUN_TO_DONE_SPLIT_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names, recording each decision via update_registry) until its "
    "status is \"done\". There are two events per car: a driving event (record its own "
    "outcome and event_state as complete once the car has arrived -- don't decide where "
    "it parks yet, that's the separate parking event's own job) and a parking event (look "
    "up what's already taken, then record via update_registry that car's own location, "
    "plus that event's own outcome and event_state). Don't narrate anything back to me."
)


@pytest.mark.live
def test_parking_split_across_two_events_per_car(tmp_path):
    """Same first-come-first-served facts as test_car_parking_core_sim (car_b
    arrives first, car_c second, car_a last) but each car's drive and its
    parking decision are separate, pre-planned events -- car_a_drive/
    car_a_park, etc. -- rather than one combined car_a_trip. Checks final
    location for each car, that all six events reached event_state
    complete, and order evidence via each car's location write being
    time-stamped with its own *parking* event's end_time (not its driving
    event's), confirming the spot was assigned once that car's own parking
    event resolved.
    """
    save_dir = tmp_path / "test_save"

    with HeadlessSession(save_dir) as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={PARKING_SPLIT_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_SPLIT_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _parked_at(_location(r, "car_b"), "parking_spot_1"), (
            "Car B should be first to actually arrive (it left earlier than Car C by more "
            f"than their trip-length difference) and take the first spot -- narration: {narration!r}"
        )
        assert _parked_at(_location(r, "car_c"), "parking_spot_2"), (
            "Car C should be second to arrive (after Car B, before Car A) and take the "
            f"remaining dedicated spot -- narration: {narration!r}"
        )
        assert _parked_at(_location(r, "car_a"), "street"), (
            "Car A starts first but has the longest drive, so it should actually arrive "
            f"last and end up parked on the street -- narration: {narration!r}"
        )

        states = _event_states(r)
        for alias in ("car_a_drive", "car_a_park", "car_b_drive", "car_b_park", "car_c_drive", "car_c_park"):
            assert states.get(alias) == "complete", (alias, states)

        times = {alias: write_time(r, "location", alias) for alias in ("car_b", "car_c", "car_a")}
        assert times["car_b"] == pytest.approx(1030), (
            f"car_b's location should be recorded at car_b_park's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_c"] == pytest.approx(1090), (
            f"car_c's location should be recorded at car_c_park's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_a"] == pytest.approx(1810), (
            f"car_a's location should be recorded at car_a_park's own end_time -- {times}, narration: {narration!r}"
        )
