"""Regressions for this directory's scenario.yaml: ../parking's puzzle, decided by collision detection.

Same events and intended outcome as ../parking, but the world is described
only by position/velocity/mass/radius -- a car's parked spot is checked via
story_simulator.physics.check_collisions (inside the spot, clear of every
other car), not by reading back a freeform `location` phrase.
"""

import asyncio
from pathlib import Path
from textwrap import dedent
from typing import ClassVar

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.expected_fixtures import assert_subset

from conftest import _make_ctx, update_registry
from story_simulator.config import registry_url
from story_simulator.mcp_server import advance_simulation, start_world
from story_simulator.physics import check_collisions
from test_human_validated.helpers import (
    create_session,
    start_world_instruction,
    _assert_write_order,
)

SCENARIO_DIR = Path(__file__).parent
CARS = ("car_a", "car_b", "car_c")


def _assert_no_car_collisions(r: Registrar) -> None:
    for car in CARS:
        hits = check_collisions(r, car)["collides_with"]
        assert not hits, f"{car} overlaps {hits}"


class TestDeterministicWalkthrough:
    """No LLM -- drives advance_simulation directly with predetermined answers."""

    pytestmark = pytest.mark.slow

    _HOST_FRAMING = (
        "Decide the answer yourself, standing in for whichever role this call "
        "needs (a player's own absent character, an NPC, a base-module entity "
        "whose end_time has been reached, ...) -- don't wait for input and "
        "don't hand this off."
    )

    # Region centers, copied from scenario.yaml.
    CENTER: ClassVar[dict[str, tuple[float, float]]] = {
        "restaurant": (0, 0),
        "parking_spot_1": (10, 0),
        "parking_spot_2": (10, 6),
        "street": (0, -20),
    }

    # (event_alias, car_alias, outcome, region the car ends up in, end_time).
    # Order matches pop_event's sort (soonest end_time first).
    WALKTHROUGH: ClassVar[list[tuple[str, str, str, str, int]]] = [
        ("car_b_drive", "car_b", "car_b_drive resolved -- car_b arrived.", "restaurant", 1020),
        ("car_b_park", "car_b", "car_b_park resolved -- car_b parked in parking_spot_1.", "parking_spot_1", 1030),
        ("car_c_drive", "car_c", "car_c_drive resolved -- car_c arrived.", "restaurant", 1080),
        ("car_c_park", "car_c", "car_c_park resolved -- car_c parked in parking_spot_2.", "parking_spot_2", 1090),
        ("car_a_drive", "car_a", "car_a_drive resolved -- car_a arrived.", "restaurant", 1800),
        ("car_a_park", "car_a", "car_a_park resolved -- parking_spot_1/2 blocked, car_a parked on the street.", "street", 1810),
    ]

    def _resolve_prompt(self, alias: str, end_time: float) -> str:
        return (
            f"{self._HOST_FRAMING}\n\n"
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

    def _plan_prompt(self, alias: str) -> str:
        return (
            f"{self._HOST_FRAMING}\n\n"
            f"Given how {alias} just resolved, does anything new need to "
            f"happen as a result? If so, create it now: one or more new "
            f"event entities (their own start_time/duration/event_state/"
            f"involved_entity) via update_registry. If nothing follows "
            f"from this, just say so -- no new events needed."
        )

    def test_scenario_seeds_no_collisions(self, tmp_path):
        """Turn zero: every car is at rest, apart, and outside every parking region."""
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx, scenario_dir=str(SCENARIO_DIR))
        r = Registrar.load(registry_url(save_dir))

        _assert_no_car_collisions(r)
        for car in CARS:
            assert r.safe_view_current("velocity.x", car).to_scalar() == 0
            assert check_collisions(r, car)["inside"] == []

    def test_full_walkthrough_collision_checked(self, tmp_path):
        """Drives all six events, checking geometry after every write."""
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx, scenario_dir=str(SCENARIO_DIR))
        r = Registrar.load(registry_url(save_dir))

        result = asyncio.run(advance_simulation(ctx))
        for event_alias, car_alias, outcome, region, end_time in self.WALKTHROUGH:
            assert result["status"] == "input_required"
            assert result["prompt"] == self._resolve_prompt(event_alias, end_time)

            # The "perfect" answer: the car comes to rest at the region's center.
            x, y = self.CENTER[region]
            update_registry(
                dedent(f"""\
                    {event_alias}:
                        - outcome:
                            value: {outcome}
                        - event_state:
                            value: complete
                    {car_alias}:
                        - position:
                            x: {x}
                            y: {y}
                            z: 0
                        - velocity:
                            x: 0
                            y: 0
                            z: 0
                    """),
                ctx=ctx,
            )
            assert region in check_collisions(r, car_alias)["inside"]
            _assert_no_car_collisions(r)

            result = asyncio.run(
                advance_simulation(ctx, resume_token=result["resume_token"], answer=f"{event_alias} resolved.")
            )
            assert result["prompt"] == self._plan_prompt(event_alias)
            result = asyncio.run(
                advance_simulation(ctx, resume_token=result["resume_token"], answer="No new events needed.")
            )

        assert result == {"status": "done", "narration": "Nothing scheduled."}

        # car_a was turned away by collision: placed at either spot's center,
        # it would overlap the car already parked there.
        for spot, parked in (("parking_spot_1", "car_b"), ("parking_spot_2", "car_c")):
            x, y = self.CENTER[spot]
            assert check_collisions(r, "car_a", x, y)["collides_with"] == [parked]


class TestLiveWalkthrough:
    # car alias -> region its final position should lie inside.
    EXPECTED_REGION: ClassVar[dict[str, str]] = {
        "car_b": "parking_spot_1",
        "car_c": "parking_spot_2",
        "car_a": "street",
    }

    EXPECTED_EVENT_STATE: ClassVar[dict[str, str]] = {
        "car_a_drive": "complete",
        "car_a_park": "complete",
        "car_b_drive": "complete",
        "car_b_park": "complete",
        "car_c_drive": "complete",
        "car_c_park": "complete",
    }

    # Each car's final position should be stamped with its parking event's end_time.
    EXPECTED_WRITE_ORDER: ClassVar[dict[str, object]] = {
        "component_type": "position",
        "times": {"car_b": 1030, "car_c": 1090, "car_a": 1810},
    }

    @pytest.mark.live
    def test_scenario_resolves_correctly(self, tmp_path: Path, live_trial):
        """Runs to completion under a live session, then checks final geometry."""
        save_dir = tmp_path / "test_save"

        with create_session(
            save_dir, turn_timeout=420, session_timeout=420, subagent_time_budget_seconds=90
        ) as session:
            print(f"agent session trace: {session.trace_path}")
            live_trial.id = str(session.trace_path)
            narration = session.send_turn(start_world_instruction(session, save_dir, SCENARIO_DIR))
            r = Registrar.load(registry_url(save_dir))

            try:
                for car, region in self.EXPECTED_REGION.items():
                    report = check_collisions(r, car)
                    assert region in report["inside"], f"{car} should be inside {region}: {report}"
                _assert_no_car_collisions(r)

                event_states = {
                    alias: r.safe_view_current("event_state.value", alias).to_scalar()
                    for alias in self.EXPECTED_EVENT_STATE
                }
                assert_subset("event_state", self.EXPECTED_EVENT_STATE, event_states)
                _assert_write_order(r, self.EXPECTED_WRITE_ORDER)
            except AssertionError as exc:
                raise AssertionError(f"{exc} -- narration: {narration!r}") from exc
