"""Live regressions for this directory's own scenario.yaml: a
bare arrival-order check with nothing else to reason about -- three cars,
one race, each car's own `race_placement` recorded directly. Permanent
regression, checked exactly via that dedicated component rather than by
matching substrings in freeform outcome text, which risks a false
positive on a coincidental wording match.

Two tests, along a deliberately different axis from each other (which
responder answers each event's judgment call, not which scenario runs):

- test_resolves_correctly_via_host_responder: the *connected* model does
  the resolve/plan reasoning itself.
- test_resolves_and_persists_via_keyed_subagent: keyed_subagent (DeepSeek
  by default) does the actual reasoning and update_registry writes
  in-process instead, with the connected model's job narrowed to just
  driving advance_simulation to "done". Not a test of keyed_subagent's
  own tool-calling mechanics (dispatch, iteration cap, usage logging,
  ...) -- that lives in emc2p's own tests/agents/test_tool_calling_loop.py.
  What this checks is simulation correctness (does the race still
  resolve in the right order, with the right timing) and CLAUDE.md's own
  re-export-on-every-update_registry invariant (save_dir/world/ actually
  gets created/updated), independent of which responder is doing the
  driving.

Deliberately checks only *final* state, not turn-by-turn state -- each
test runs the whole scenario in one open-ended instruction, in as many
or as few advance_simulation round-trips as the model wants. Order
evidence instead comes from each expected write's own recorded world
time (helpers._assert_write_order), confirming it was recorded while its
own event resolved, not retroactively.

Both instructions below are deliberately generic ("run to done") -- any
reasoning a responder needs to resolve a specific event correctly (what
to look up, what to record, and how) comes from the MCP server's own
resolve/plan prompts (see `core.resolve_event`/`plan_events`), not from
this test smuggling in scenario-specific hints no real deployment would
provide.
"""

from pathlib import Path

import pytest

from emc2p.testing.expected_fixtures import assert_subset
from test_human_validated.helpers import (
    create_session,
    _assert_write_order,
    _event_states,
    _load_registrar,
    _placement,
)

SCENARIO_DIR = Path(__file__).parent

# alias -> expected race_placement.value (1-indexed finishing position).
EXPECTED_RACE_PLACEMENT = {"car_b": 1, "car_c": 2, "car_a": 3}

# alias -> expected event_state.value, once the whole race has resolved.
EXPECTED_EVENT_STATE = {
    "car_b_trip": "complete",
    "car_c_trip": "complete",
    "car_a_trip": "complete",
}

# Order evidence: each car's race_placement write should be time-stamped
# with its own trip event's end_time (world time -- see
# core._next_time_stamp), confirming it was recorded while that car's own
# event resolved, not retroactively or out of turn.
EXPECTED_WRITE_ORDER = {
    "component_type": "race_placement",
    "times": {"car_b": 1020, "car_c": 1080, "car_a": 1800},
}


def _check_race(r) -> None:
    """race_placement is a plain int field the model fills directly -- an exact
    match (assert_subset) is the right check, no phrasing to be lenient about."""
    placements = {alias: _placement(r, alias) for alias in EXPECTED_RACE_PLACEMENT}
    assert_subset("race_placement", EXPECTED_RACE_PLACEMENT, placements)


# Deliberately one open-ended instruction, not one per event -- checks
# the final result and order, not turn count.
_RUN_TO_DONE_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (recording each "
    "decision via update_registry) until its status is \"done\". Don't "
    "narrate anything back to me."
)

_DRIVE_TO_DONE_INSTRUCTION = (
    "Call advance_simulation repeatedly until its status is \"done\". If it ever comes back "
    "with status \"input_required\", just call it again with the same resume_token and a "
    "short answer telling it to keep going -- don't try to answer the substance of any "
    "prompt yourself. Don't narrate anything back to me."
)


@pytest.mark.live
def test_resolves_correctly_via_host_responder(tmp_path: Path):
    """Run to completion under a live "host"-responder session, then check
    final registry state against this module's own EXPECTED_* constants
    (race_placement exactly, event_state/write-order generically)."""
    save_dir = tmp_path / "test_save"

    # This test's whole point is the *connected* model's own reasoning --
    # explicit override of create_session's keyed_subagent default.
    with create_session(save_dir, responder="host") as session:
        print(f"agent session trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)
        try:
            _check_race(r)
            assert_subset("event_state", EXPECTED_EVENT_STATE, _event_states(r))
            _assert_write_order(r, EXPECTED_WRITE_ORDER)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc


@pytest.mark.live
def test_resolves_and_persists_via_keyed_subagent(tmp_path: Path):
    """Does the simulation still resolve correctly, and does the write
    actually persist, when keyed_subagent (not the connected model) is
    doing the resolve/plan reasoning and the update_registry writes?

    Checks two things: (1) the same correctness checks
    test_resolves_correctly_via_host_responder runs (car_b first, car_c
    second, car_a third, all three trip events complete, each placement
    time-stamped with its own trip event's end_time), and (2)
    save_dir/world/ actually exists and isn't empty afterward --
    CLAUDE.md's own re-export-on-every-update_registry invariant.
    """
    save_dir = tmp_path / "test_save"

    # Both timeouts raised well past create_session's own 120s/240s defaults --
    # keyed_subagent's own nested DeepSeek rounds cost real time inside each call.
    with create_session(save_dir, turn_timeout=420, session_timeout=420) as session:  # responder="keyed_subagent", the default
        print(f"agent session trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_DRIVE_TO_DONE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)
        try:
            _check_race(r)
            assert_subset("event_state", EXPECTED_EVENT_STATE, _event_states(r))
            _assert_write_order(r, EXPECTED_WRITE_ORDER)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc

        world_dir = save_dir / "world"
        assert world_dir.is_dir(), (
            f"save_dir/world/ was never created -- keyed_subagent's update_registry calls "
            f"never actually persisted anything. narration: {narration!r}"
        )
        assert any(world_dir.iterdir()), f"save_dir/world/ exists but is empty. narration: {narration!r}"

