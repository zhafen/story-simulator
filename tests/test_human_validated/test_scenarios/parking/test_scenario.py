"""Regressions for this directory's scenario.yaml: three cars compete for two parking spots.

TestDeterministicWalkthrough drives advance_simulation directly with
scripted answers (no LLM); TestLiveWalkthrough drives the same scenario
via a real model, checking only final state. Each class owns its own
EXPECTED_*/constants; only SCENARIO_DIR is shared.
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
from test_human_validated.helpers import (
    RUN_TO_DONE_INSTRUCTION,
    create_session,
    _assert_write_order,
    _event_states,
)

SCENARIO_DIR = Path(__file__).parent


class TestDeterministicWalkthrough:
    """No LLM, no MCP round-trip -- drives advance_simulation directly with predetermined answers.

    See module docstring for why this exists alongside TestLiveWalkthrough.
    """

    # A real db-backed walkthrough (six events, twelve round-trips) --
    # no LLM, but not fast enough for the default tier.
    pytestmark = pytest.mark.slow

    _HOST_FRAMING = (
        "Decide the answer yourself, standing in for whichever role this call "
        "needs (a player's own absent character, an NPC, a base-module entity "
        "whose end_time has been reached, ...) -- don't wait for input and "
        "don't hand this off."
    )

    # (event_alias, car_alias, outcome, location written or None, end_time).
    # Order matches pop_event's sort (soonest end_time first); see scenario.yaml.
    WALKTHROUGH: ClassVar[list[tuple[str, str, str, str | None, int]]] = [
        ("car_b_drive", "car_b", "car_b_drive resolved -- car_b arrived.", None, 1020),
        ("car_b_park", "car_b", "car_b_park resolved -- car_b parked in parking_spot_1.", "parking_spot_1", 1030),
        ("car_c_drive", "car_c", "car_c_drive resolved -- car_c arrived.", None, 1080),
        ("car_c_park", "car_c", "car_c_park resolved -- car_c parked in parking_spot_2.", "parking_spot_2", 1090),
        ("car_a_drive", "car_a", "car_a_drive resolved -- car_a arrived.", None, 1800),
        ("car_a_park", "car_a", "car_a_park resolved -- car_a parked on the street.", "street", 1810),
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

    def test_end_time_order_matches_true_arrival_order(self, tmp_path):
        """Confirms car_b_drive resolves before car_b_park, car_c_drive/park, then car_a_drive/park.

        Computed from the scenario's own start_time+duration, independent of any model.
        """
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx, scenario_dir=str(SCENARIO_DIR))

        result = asyncio.run(advance_simulation(ctx))
        assert result["status"] == "input_required"
        assert result["prompt"] == self._resolve_prompt("car_b_drive", end_time=1020)

    def test_full_walkthrough_exact_prompts_and_registry_state(self, tmp_path):
        """Drives all six events to completion, asserting exact prompt text and registry state at each step."""
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx, scenario_dir=str(SCENARIO_DIR))
        r = Registrar.load(registry_url(save_dir))

        result = asyncio.run(advance_simulation(ctx))
        for event_alias, car_alias, outcome, location, end_time in self.WALKTHROUGH:
            assert result["status"] == "input_required"
            assert result["prompt"] == self._resolve_prompt(event_alias, end_time)
            assert result["responder"] == "host"

            # The "perfect" answer to a resolve prompt: outcome/event_state, plus
            # location if this is a parking event, matching the puzzle's known-correct solution.
            if location is not None:
                yaml_string = dedent(f"""\
                    {event_alias}:
                        - outcome:
                            value: {outcome}
                        - event_state:
                            value: complete
                    {car_alias}:
                        - location:
                            value: {location}
                    """)
            else:
                yaml_string = dedent(f"""\
                    {event_alias}:
                        - outcome:
                            value: {outcome}
                        - event_state:
                            value: complete
                    """)
            update_registry(yaml_string, ctx=ctx)
            if location is not None:
                assert r.get_current_value("location", alias=car_alias) == location, (
                    f"{car_alias}.location should read back exactly what was just "
                    f"written -- if this fails, update_registry's write didn't "
                    f"actually persist/read back, independent of anything a model "
                    f"decided"
                )

            result = asyncio.run(
                advance_simulation(ctx, resume_token=result["resume_token"], answer=f"{event_alias} resolved.")
            )
            assert result["status"] == "input_required"
            assert result["prompt"] == self._plan_prompt(event_alias)

            result = asyncio.run(
                advance_simulation(ctx, resume_token=result["resume_token"], answer="No new events needed.")
            )

        assert result == {"status": "done", "narration": "Nothing scheduled."}

        # Final state: every car ended up exactly where the puzzle says it should.
        for event_alias, car_alias, outcome, location, end_time in self.WALKTHROUGH:
            if location is not None:
                assert r.get_current_value("location", alias=car_alias) == location


class TestLiveWalkthrough:
    # alias -> substring in the car's recorded location.value (see
    # _parked_at) -- not exact, since a model's phrasing varies.
    EXPECTED_LOCATION: ClassVar[dict[str, str]] = {
        "car_b": "parking_spot_1",
        "car_c": "parking_spot_2",
        "car_a": "street",
    }

    # alias -> expected event_state.value, once every drive/park event has resolved.
    # ClassVar: read-only test data pytest test classes can't set via __init__.
    EXPECTED_EVENT_STATE: ClassVar[dict[str, str]] = {
        "car_a_drive": "complete",
        "car_a_park": "complete",
        "car_b_drive": "complete",
        "car_b_park": "complete",
        "car_c_drive": "complete",
        "car_c_park": "complete",
    }

    # Order evidence: each location write should be time-stamped with its
    # own *parking* event's end_time, not its driving event's.
    EXPECTED_WRITE_ORDER: ClassVar[dict[str, object]] = {
        "component_type": "location",
        "times": {"car_b": 1030, "car_c": 1090, "car_a": 1810},
    }

    @pytest.mark.live
    def test_scenario_resolves_correctly(self, tmp_path: Path):
        """Runs to completion under a live "host"-responder session, then checks final state."""
        save_dir = tmp_path / "test_save"

        # Raised timeouts: six resolve+plan steps routinely exceed the
        # 120s/240s defaults, timing out mid-event otherwise.
        with create_session(save_dir, turn_timeout=420, session_timeout=420) as session:
            print(f"agent session trace: {session.trace_path}")
            narration = session.send_turn(
                f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
                f"to open a story-simulator world. Then {RUN_TO_DONE_INSTRUCTION}"
            )
            r = Registrar.load(registry_url(save_dir))

            try:
                # Check parking locations along the way
                for alias, spot in self.EXPECTED_LOCATION.items():

                    location = r.get_current_value("location", alias=alias)
                    assert location is not None and spot in location, (
                        f"{alias} should be parked at {spot}"
                    )

                assert_subset("event_state", self.EXPECTED_EVENT_STATE, _event_states(r))
                _assert_write_order(r, self.EXPECTED_WRITE_ORDER)
            except AssertionError as exc:
                raise AssertionError(f"{exc} -- narration: {narration!r}") from exc