"""Deterministic sibling of test_parking_split_live.py's own deterministic
sibling relationship (test_car_parking_deterministic.py <-> the live
combined-scenario test, now removed) -- for
tests/data/scenarios/parking_dynamic, task #57's "Planning-events testing".

Drives the same first-come-first-served puzzle as
tests/data/scenarios/parking/scenario.yaml and .../parking_split/
scenario.yaml, but this scenario seeds only each car's driving leg
(car_a_drive/car_b_drive/car_c_drive) -- there is no car_X_park event
anywhere in the seed. Each car's own parking event has to be created here,
by hand, as the "perfect" answer to that driving event's own plan_events
prompt -- the same update_registry call a real responder makes to schedule
a follow-up (see tests/test_event_loop.py::
test_plan_step_creates_a_new_event_that_gets_picked_up_next for the
generic, synthetic-event version of this same mechanism). This is the
no-LLM system-correctness check for the event-planning framework thread
(docs/manifest/history.yaml: project_history.combined_parking_test_removed's
own follow-up note): if this fails, the loop itself (pop/plan/resolve
ordering, resume_token bookkeeping, a new event created mid-plan not
getting picked up) is broken, independent of any model's own judgment.
"""

import asyncio
from pathlib import Path

from emc2p.registrar import Registrar

from conftest import _make_ctx, update_registry
from story_simulator.config import registry_url
from story_simulator.mcp_server import advance_simulation, start_world

REPO_ROOT = Path(__file__).parent.parent.parent
PARKING_DYNAMIC_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking_dynamic"

_HOST_FRAMING = (
    "Decide the answer yourself, standing in for whichever role this call "
    "needs (a player's own absent character, an NPC, a base-module entity "
    "whose end_time has been reached, ...) -- don't wait for input and "
    "don't hand this off."
)


def _location(save_dir, alias: str) -> str | None:
    """Read `alias`'s current location.value directly from the registry."""
    return Registrar.load(registry_url(save_dir)).get_current_value("location", alias=alias)


def _resolve_prompt(alias: str, end_time: float) -> str:
    return (
        f"{_HOST_FRAMING}\n\n"
        f"{alias}'s end_time (world time {end_time:g}) has been reached. "
        f"Nothing else with an earlier end_time is still unresolved -- if "
        f"another entity's own event hasn't reached event_state: complete "
        f"yet (check via view_entity/view_registry, not assumed from its "
        f"start_time or where it appears in a table), treat it as not "
        f"having happened yet. Look up whatever you need (view_entity/"
        f"view_registry, including its involved_entity links) to work out "
        f"what happens, then "
        f"record it: {alias}'s own "
        f"outcome, {alias}'s own event_state (complete if this fully "
        f"resolves it, interrupted if something cuts it short), and "
        f"anything it changes about the entities it involves -- write "
        f"those changes directly onto each affected entity itself, using "
        f"whichever component type actually fits (view_entity on the "
        f"component type's own name, e.g. view_entity('location'), shows "
        f"its field descriptions if you're unsure which one or how to "
        f"phrase it), not only described in {alias}'s own outcome text -- "
        f"all via update_registry."
    )


def _plan_prompt(alias: str) -> str:
    return (
        f"{_HOST_FRAMING}\n\n"
        f"Given how {alias} just resolved, does anything new need to "
        f"happen as a result? If so, create it now: one or more new "
        f"event entities (their own start_time/duration/event_state/"
        f"involved_entity) via update_registry. If nothing follows "
        f"from this, just say so -- no new events needed."
    )


def _mark_arrived(ctx, drive_alias: str) -> None:
    """The "perfect" answer to a driving event's own resolve prompt:
    record only that the car arrived -- not where it parks, that's the
    not-yet-scheduled parking event's own job."""
    update_registry(
        f"{drive_alias}:\n"
        f"    - outcome:\n"
        f"        value: {drive_alias} resolved -- the car arrived near the restaurant.\n"
        f"    - event_state:\n"
        f"        value: complete\n",
        ctx=ctx,
    )


def _plan_parking_event(ctx, drive_alias: str, park_alias: str, car_alias: str, arrival_time: float) -> None:
    """The "perfect" answer to a driving event's own plan prompt: create
    the car's parking event now, since nothing pre-planned it.

    Mirrors parking_split/scenario.yaml's own convention (a short, fixed
    10-second duration starting the moment the car arrives) so pop_event's
    mechanical sort still resolves every car's driving leg before its own
    parking decision, without ever tying a driving and parking event at
    the same end_time -- but decided here, live, rather than pre-authored
    into the seed.
    """
    update_registry(
        f"{park_alias}:\n"
        f"    - event:\n"
        f"        start_time: {arrival_time:g}\n"
        f"        duration: 10\n"
        f"    - event_state:\n"
        f"        value: planned\n"
        f"    - involved_entity:\n"
        f"        - value: {car_alias}\n"
        f"        - value: restaurant\n"
        f"    - description:\n"
        f"        value: {car_alias}'s parking decision, now that it has arrived.\n",
        ctx=ctx,
    )


def _mark_parked(ctx, park_alias: str, car_alias: str, location: str) -> None:
    """The "perfect" answer to a parking event's own resolve prompt:
    record the event's own outcome/event_state, and the car's own location."""
    update_registry(
        f"{park_alias}:\n"
        f"    - outcome:\n"
        f"        value: {park_alias} resolved -- {car_alias} {location}.\n"
        f"    - event_state:\n"
        f"        value: complete\n"
        f"\n"
        f"{car_alias}:\n"
        f"    - location:\n"
        f"        value: {location}\n",
        ctx=ctx,
    )


def test_no_parking_events_scheduled_at_start(tmp_path):
    """The whole point of this scenario: only driving events exist until
    a plan step creates one -- confirmed here independent of the rest of
    the walkthrough below."""
    ctx = _make_ctx()
    save_dir = tmp_path / "save"
    start_world(str(save_dir), ctx, scenario_dir=str(PARKING_DYNAMIC_SCENARIO_DIR))

    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["prompt"] == _resolve_prompt("car_b_drive", end_time=1020), (
        "The soonest-due event should be car_b's drive (end_time 1020) -- "
        "if a car_X_park event is already due instead, one got pre-planned "
        "into the seed after all."
    )


def test_full_walkthrough_dynamically_planned_parking(tmp_path):
    """Drives all three cars' driving legs to completion, creating each
    car's parking event live (during that drive's own plan step) rather
    than finding it pre-planned, then resolves each parking event too --
    asserting exact prompts and registry state at every step, the same
    way test_car_parking_deterministic.py's full walkthrough does for the
    pre-planned/combined scenario.
    """
    ctx = _make_ctx()
    save_dir = tmp_path / "save"
    start_world(str(save_dir), ctx, scenario_dir=str(PARKING_DYNAMIC_SCENARIO_DIR))

    # (drive_alias, park_alias, car_alias, arrival_time, park_end_time, location)
    plan = [
        ("car_b_drive", "car_b_park", "car_b", 1020, 1030, "parked in parking_spot_1"),
        ("car_c_drive", "car_c_park", "car_c", 1080, 1090, "parked in parking_spot_2"),
        ("car_a_drive", "car_a_park", "car_a", 1800, 1810, "parked on the street"),
    ]

    result = asyncio.run(advance_simulation(ctx))
    for drive_alias, park_alias, car_alias, arrival_time, park_end_time, location in plan:
        # -- Driving event: resolve (just arrival, no parking decision yet) --
        assert result["status"] == "input_required"
        assert result["prompt"] == _resolve_prompt(drive_alias, arrival_time)
        assert result["responder"] == "host"

        _mark_arrived(ctx, drive_alias)
        assert _location(save_dir, car_alias) is None, (
            f"{car_alias} shouldn't have a location yet -- the driving event's own "
            f"resolve step isn't supposed to decide where it parks."
        )

        result = asyncio.run(
            advance_simulation(ctx, resume_token=result["resume_token"], answer=f"{drive_alias} resolved.")
        )

        # -- Driving event: plan (this is what schedules the parking event -- nothing did it up front) --
        assert result["status"] == "input_required"
        assert result["prompt"] == _plan_prompt(drive_alias)

        _plan_parking_event(ctx, drive_alias, park_alias, car_alias, arrival_time)
        result = asyncio.run(
            advance_simulation(
                ctx, resume_token=result["resume_token"], answer=f"Scheduled {park_alias} next."
            )
        )

        # -- Parking event: resolve (first-come-first-served spot assignment) --
        assert result["status"] == "input_required"
        assert result["prompt"] == _resolve_prompt(park_alias, park_end_time), (
            f"The dynamically-created {park_alias} should be exactly what pop_event "
            f"picks up next -- as poppable as anything pre-planned from the seed."
        )

        _mark_parked(ctx, park_alias, car_alias, location)
        assert _location(save_dir, car_alias) == location

        result = asyncio.run(
            advance_simulation(ctx, resume_token=result["resume_token"], answer=f"{park_alias} resolved.")
        )

        # -- Parking event: plan (nothing follows from a car parking) --
        assert result["status"] == "input_required"
        assert result["prompt"] == _plan_prompt(park_alias)

        result = asyncio.run(
            advance_simulation(ctx, resume_token=result["resume_token"], answer="No new events needed.")
        )

    assert result == {"status": "done", "narration": "Nothing scheduled."}

    # Final state: every car ended up exactly where the puzzle says it should.
    for _drive_alias, _park_alias, car_alias, _arrival_time, _park_end_time, location in plan:
        assert _location(save_dir, car_alias) == location
