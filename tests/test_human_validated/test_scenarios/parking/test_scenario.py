"""Regressions for this directory's own scenario.yaml: three cars drive
to a restaurant with only two parking spots, first-come-first-served --
each car's drive and its own parking decision are separate, pre-planned
events (a driving event that ends on arrival, then a parking event that
assigns a spot), not bundled into one combined "trip" resolution.

Two classes, along a deliberately different axis from each other (how
the walkthrough is driven, not which scenario runs):

- TestDeterministicWalkthrough: drives advance_simulation/update_registry
  directly with hand-scripted "perfect" answers -- no LLM, no MCP
  round-trip, no cost, no flakiness. Asserts *exact* prompt text,
  end_time order, and registry state at every step, so a live-test
  failure (below) can be checked against this first: if this still
  passes, the mechanism is sound and the live failure is the model; if
  this fails too, it's a real bug independent of any model at all.
- TestLiveWalkthrough: the same scenario driven by a real connected
  model over a real session, checking only *final* registry state (not
  turn-by-turn) against this module's own EXPECTED_* constants.

Both start from the same scenario.yaml so a live-test failure and its
deterministic counterpart are always comparing apples to apples -- no
risk of the two drifting into subtly different fixtures over time.

The session in TestLiveWalkthrough is started with
helpers.RUN_TO_DONE_INSTRUCTION, deliberately generic ("run to done") and
shared rather than redefined per scenario -- any reasoning a responder
needs to resolve a specific event correctly (what to look up, what to
record, and how) comes from the MCP server's own resolve/plan prompts
(see `core.resolve_event`/`plan_events`), not from this test smuggling in
scenario-specific hints no real deployment would provide.
"""

import asyncio
from pathlib import Path

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

_HOST_FRAMING = (
    "Decide the answer yourself, standing in for whichever role this call "
    "needs (a player's own absent character, an NPC, a base-module entity "
    "whose end_time has been reached, ...) -- don't wait for input and "
    "don't hand this off."
)


def _parked_at(location: str | None, spot: str) -> bool:
    """Loosely checks a recorded `location` value names `spot` (e.g.
    "parking_spot_1" or "street"), not any one exact phrasing.

    `location`'s own schema (manifest/builtins.yaml) calls it a "short
    freeform phrase" -- a model's correct answer can reasonably come out
    phrased several ways ("parked in
    parking_spot_1" vs. just "parking_spot_1") -- the model shouldn't
    have to guess the one exact wording a test hardcodes. Takes the
    value directly (e.g. from `registrar.get_current_value("location",
    alias=alias)`) rather than reading it itself.

    Scenario-specific, not shared -- tests/location_write_harness.py
    keeps its own copy rather than importing this one.
    """
    return location is not None and spot in location


# alias -> a substring that must appear in that car's recorded
# location.value (see _parked_at above) -- not an exact string, since a
# live model's own phrasing of "parked in parking_spot_1" reasonably varies.
EXPECTED_LOCATION = {
    "car_b": "parking_spot_1",
    "car_c": "parking_spot_2",
    "car_a": "street",
}

# alias -> expected event_state.value, once every drive/park event has resolved.
EXPECTED_EVENT_STATE = {
    "car_a_drive": "complete",
    "car_a_park": "complete",
    "car_b_drive": "complete",
    "car_b_park": "complete",
    "car_c_drive": "complete",
    "car_c_park": "complete",
}

# Order evidence: each car's location write should be time-stamped with its
# own *parking* event's end_time (not its driving event's), confirming the
# spot was assigned once that car's own parking event resolved.
EXPECTED_WRITE_ORDER = {
    "component_type": "location",
    "times": {"car_b": 1030, "car_c": 1090, "car_a": 1810},
}

# (event_alias, car_alias, outcome text, location written or None if this
# event shouldn't write one yet, that event's own end_time). Order matches
# pop_event's own mechanical sort (soonest end_time first): each car's
# driving event ends before its own parking event starts, and no driving
# and parking event are ever tied at the same end_time (see scenario.yaml's
# own file_info for why the timings were chosen that way).
WALKTHROUGH = [
    ("car_b_drive", "car_b", "car_b_drive resolved -- car_b arrived.", None, 1020),
    ("car_b_park", "car_b", "car_b_park resolved -- car_b parked in parking_spot_1.", "parking_spot_1", 1030),
    ("car_c_drive", "car_c", "car_c_drive resolved -- car_c arrived.", None, 1080),
    ("car_c_park", "car_c", "car_c_park resolved -- car_c parked in parking_spot_2.", "parking_spot_2", 1090),
    ("car_a_drive", "car_a", "car_a_drive resolved -- car_a arrived.", None, 1800),
    ("car_a_park", "car_a", "car_a_park resolved -- car_a parked on the street.", "street", 1810),
]


def _check_parking(r) -> None:
    """location is a freeform phrase (see _parked_at above) -- a live model's
    correct answer can reasonably come out phrased several ways, so this checks
    a substring rather than assert_subset's exact match."""
    for alias, spot in EXPECTED_LOCATION.items():
        assert _parked_at(r.get_current_value("location", alias=alias), spot), (
            f"{alias} should be parked at {spot}"
        )


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


class TestDeterministicWalkthrough:
    """No LLM, no MCP round-trip: drives advance_simulation/update_registry
    directly, in-process, with predetermined correct answers. See this
    module's own docstring for why this exists alongside
    TestLiveWalkthrough below."""

    # A real db-backed walkthrough (six events, twelve advance_simulation
    # round-trips) -- no LLM involved, but not fast enough for the default
    # tier either.
    pytestmark = pytest.mark.slow

    def _location(self, save_dir, alias: str) -> str | None:
        """Read `alias`'s current location.value directly from the registry.

        Same read path (view_current on a time_dimension'd component) a
        live test failure needs cross-checking against.
        """
        return Registrar.load(registry_url(save_dir)).get_current_value("location", alias=alias)

    def _mark_resolved(self, ctx, event_alias: str, car_alias: str, outcome: str, location: str | None) -> None:
        """The "perfect" answer to a resolve prompt: record the event's own
        outcome/event_state, and -- only for a parking event, not a driving
        one -- the car's own location.

        Exactly what a correct responder is asked to do, matching the
        puzzle's known-correct solution (see this scenario's own
        description.value).
        """
        location_block = (
            f"\n{car_alias}:\n    - location:\n        value: {location}\n"
            if location is not None else ""
        )
        update_registry(
            f"{event_alias}:\n"
            f"    - outcome:\n"
            f"        value: {outcome}\n"
            f"    - event_state:\n"
            f"        value: complete\n"
            f"{location_block}",
            ctx=ctx,
        )

    def test_end_time_order_matches_true_arrival_order(self, tmp_path):
        """car_b_drive (end_time 1020) must be served before car_b_park
        (1030), before car_c_drive (1080), before car_c_park (1090),
        before car_a_drive (1800), before car_a_park (1810).

        Computed straight from the scenario's own start_time+duration, not
        trusted from prose -- pinned down here independent of any model.
        """
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx, scenario_dir=str(SCENARIO_DIR))

        result = asyncio.run(advance_simulation(ctx))
        assert result["status"] == "input_required"
        assert result["prompt"] == _resolve_prompt("car_b_drive", end_time=1020)

    def test_full_walkthrough_exact_prompts_and_registry_state(self, tmp_path):
        """Drives all six events to completion with predetermined correct
        answers, asserting the exact prompt text and registry state at every step."""
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx, scenario_dir=str(SCENARIO_DIR))

        result = asyncio.run(advance_simulation(ctx))
        for event_alias, car_alias, outcome, location, end_time in WALKTHROUGH:
            assert result["status"] == "input_required"
            assert result["prompt"] == _resolve_prompt(event_alias, end_time)
            assert result["responder"] == "host"

            self._mark_resolved(ctx, event_alias, car_alias, outcome, location)
            if location is not None:
                assert self._location(save_dir, car_alias) == location, (
                    f"{car_alias}.location should read back exactly what was just "
                    f"written -- if this fails, update_registry's write didn't "
                    f"actually persist/read back, independent of anything a model "
                    f"decided"
                )

            result = asyncio.run(
                advance_simulation(ctx, resume_token=result["resume_token"], answer=f"{event_alias} resolved.")
            )
            assert result["status"] == "input_required"
            assert result["prompt"] == _plan_prompt(event_alias)

            result = asyncio.run(
                advance_simulation(ctx, resume_token=result["resume_token"], answer="No new events needed.")
            )

        assert result == {"status": "done", "narration": "Nothing scheduled."}

        # Final state: every car ended up exactly where the puzzle says it should.
        for event_alias, car_alias, outcome, location, end_time in WALKTHROUGH:
            if location is not None:
                assert self._location(save_dir, car_alias) == location


class TestLiveWalkthrough:
    @pytest.mark.live
    def test_scenario_resolves_correctly(self, tmp_path: Path):
        """Run to completion under a live "host"-responder session, then check
        final registry state against this module's own EXPECTED_* constants
        (location by substring, event_state/write-order generically)."""
        save_dir = tmp_path / "test_save"

        # This test's whole point is the *connected* model's own reasoning --
        # explicit override of create_session's keyed_subagent default.
        #
        # A "host"-responder run driving all six resolve+plan steps itself
        # (twice as many as the race scenario's three events) routinely needs
        # more than create_session's own 120s/240s defaults, timing out
        # mid-event otherwise -- not on anything about the simulation itself.
        with create_session(save_dir, responder="host", turn_timeout=420, session_timeout=420) as session:
            print(f"agent session trace: {session.trace_path}")
            narration = session.send_turn(
                f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
                f"to open a story-simulator world. Then {RUN_TO_DONE_INSTRUCTION}"
            )
            r = Registrar.load(registry_url(save_dir))

            try:
                _check_parking(r)
                assert_subset("event_state", EXPECTED_EVENT_STATE, _event_states(r))
                _assert_write_order(r, EXPECTED_WRITE_ORDER)
            except AssertionError as exc:
                raise AssertionError(f"{exc} -- narration: {narration!r}") from exc
