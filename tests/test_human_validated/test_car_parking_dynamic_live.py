"""Live regression for issue #57's "Planning-events testing" scope, and
the event-planning-framework follow-up noted in docs/manifest/history.yaml:
project_history.combined_parking_test_removed.

tests/test_parking_split_live.py already proved first-come-first-served
parking survives splitting each car's drive and its parking decision into
two separate events -- but both events were pre-planned into the seed
scenario from turn zero. Real gameplay schedules follow-up events live,
during a driving event's own plan step (story_simulator.core.plan_events),
not by a scenario author hand-authoring them in advance. This test keeps
the same split-events structure and the same first-come-first-served
consequence, but seeds only each car's driving leg (tests/data/scenarios/
parking_dynamic/scenario.yaml) -- the connected model has to notice, once
a car arrives, that where it parks is a separate not-yet-scheduled
decision and create that event itself via update_registry, before
resolving it.
"""

from pathlib import Path

import pytest

from test_human_validated.helpers import HeadlessSession, _event_states, _load_registrar, _parked_at
from emc2p.testing.registry_checks import write_time

REPO_ROOT = Path(__file__).parent.parent.parent
PARKING_DYNAMIC_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking_dynamic"

_RUN_TO_DONE_DYNAMIC_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names, recording each decision via update_registry) until its "
    "status is \"done\". Only each car's own driving event is pre-planned -- there is no "
    "parking event yet for any car. For a driving event's resolve step, record only that "
    "the car has arrived (don't decide where it parks yet). For that same driving event's "
    "plan step, notice that a follow-up is needed and create one new event entity for that "
    "car's own parking decision, via update_registry -- give it a start_time equal to the "
    "moment the car arrived and a short, fixed 10-second duration, plus involved_entity "
    "linking that car and the restaurant. Once that parking event itself comes due, its "
    "resolve step is where you look up what's already taken and record via update_registry "
    "that car's own location, plus that event's own outcome and event_state; its own plan "
    "step needs nothing further. Don't narrate anything back to me."
)


@pytest.mark.live
def test_parking_dynamically_planned_across_two_events_per_car(tmp_path):
    """Same first-come-first-served facts as test_parking_split_across_two_events_per_car
    (car_b arrives first, car_c second, car_a last), but this scenario's
    parking events don't exist until the connected model's own plan step
    creates them.

    Checks final location for each car, and that each car's location
    write is time-stamped with its own *parking* event's end_time (car
    arrival time + the instructed 10-second duration) rather than its
    driving event's end_time -- confirming the spot was assigned once a
    dynamically-created parking event resolved, not folded back into the
    driving event's own resolve step.
    """
    save_dir = tmp_path / "test_save"

    # This test's whole point is the *connected* model's own planning
    # decision -- explicit override of the keyed_subagent default.
    with HeadlessSession(save_dir, responder="host") as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={PARKING_DYNAMIC_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_DYNAMIC_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _parked_at(r.get_current_value("location", alias="car_b"), "parking_spot_1"), (
            "Car B should be first to actually arrive (it left earlier than Car C by more "
            f"than their trip-length difference) and take the first spot -- narration: {narration!r}"
        )
        assert _parked_at(r.get_current_value("location", alias="car_c"), "parking_spot_2"), (
            "Car C should be second to arrive (after Car B, before Car A) and take the "
            f"remaining dedicated spot -- narration: {narration!r}"
        )
        assert _parked_at(r.get_current_value("location", alias="car_a"), "street"), (
            "Car A starts first but has the longest drive, so it should actually arrive "
            f"last and end up parked on the street -- narration: {narration!r}"
        )

        states = _event_states(r)
        assert len(states) >= 6, (
            "Expected at least the three pre-planned driving events plus one "
            f"dynamically-created parking event per car -- {states}, narration: {narration!r}"
        )
        for alias, state in states.items():
            assert state == "complete", (
                f"{alias} never reached event_state complete -- {states}, narration: {narration!r}"
            )

        times = {alias: write_time(r, "location", alias) for alias in ("car_b", "car_c", "car_a")}
        assert times["car_b"] == pytest.approx(1030), (
            f"car_b's location should be recorded at its dynamically-planned parking "
            f"event's own end_time (1020 arrival + the instructed 10s duration) -- "
            f"{times}, narration: {narration!r}"
        )
        assert times["car_c"] == pytest.approx(1090), (
            f"car_c's location should be recorded at its dynamically-planned parking "
            f"event's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_a"] == pytest.approx(1810), (
            f"car_a's location should be recorded at its dynamically-planned parking "
            f"event's own end_time -- {times}, narration: {narration!r}"
        )
