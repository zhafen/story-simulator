"""Live regressions for this directory's scenario.yaml: three cars race for placement.

test_resolves_correctly_via_host_responder has the connected model reason
itself; test_resolves_and_persists_via_keyed_subagent has keyed_subagent
do it in-process. Both check only final state via race_placement/EXPECTED_*.
"""

from pathlib import Path

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.expected_fixtures import assert_subset
from story_simulator.config import registry_url
from test_human_validated.helpers import (
    RUN_TO_DONE_INSTRUCTION,
    create_session,
    _assert_write_order,
    _event_states,
)

SCENARIO_DIR = Path(__file__).parent


def _placement(registrar: Registrar, alias: str) -> int | str | None:
    """Current `race_placement.value` for an aliased car, or None if unset.

    Returns the raw value uncoerced if not int-like, so a failing assertion
    shows what was actually written. Scenario-specific, not shared.
    """
    value = registrar.get_current_value("race_placement", "value", alias)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value

# alias -> expected race_placement.value (1-indexed finishing position).
EXPECTED_RACE_PLACEMENT = {"car_b": 1, "car_c": 2, "car_a": 3}

# alias -> expected event_state.value, once the whole race has resolved.
EXPECTED_EVENT_STATE = {
    "car_b_trip": "complete",
    "car_c_trip": "complete",
    "car_a_trip": "complete",
}

# Order evidence: each race_placement write should be time-stamped with
# its own trip event's end_time, confirming it wasn't recorded out of turn.
EXPECTED_WRITE_ORDER = {
    "component_type": "race_placement",
    "times": {"car_b": 1020, "car_c": 1080, "car_a": 1800},
}


def _check_race(r) -> None:
    """race_placement is a plain int field -- exact match (assert_subset), no phrasing to allow."""
    placements = {alias: _placement(r, alias) for alias in EXPECTED_RACE_PLACEMENT}
    assert_subset("race_placement", EXPECTED_RACE_PLACEMENT, placements)


@pytest.mark.live
def test_resolves_correctly_via_host_responder(tmp_path: Path):
    """Runs to completion under a live "host"-responder session, then checks final state."""
    save_dir = tmp_path / "test_save"

    # This test's whole point is the *connected* model's own reasoning --
    # explicit override of create_session's keyed_subagent default.
    with create_session(save_dir, responder="host") as session:
        print(f"agent session trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {RUN_TO_DONE_INSTRUCTION}"
        )
        r = Registrar.load(registry_url(save_dir))
        try:
            _check_race(r)
            assert_subset("event_state", EXPECTED_EVENT_STATE, _event_states(r))
            _assert_write_order(r, EXPECTED_WRITE_ORDER)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc


@pytest.mark.live
def test_resolves_and_persists_via_keyed_subagent(tmp_path: Path):
    """Confirms the simulation still resolves and persists when keyed_subagent does the writes.

    Checks the same correctness as the host-responder test, plus that
    save_dir/world/ actually exists and isn't empty afterward.
    """
    save_dir = tmp_path / "test_save"

    # Both timeouts raised well past create_session's own 120s/240s defaults --
    # keyed_subagent's own nested DeepSeek rounds cost real time inside each call.
    with create_session(save_dir, turn_timeout=420, session_timeout=420) as session:  # responder="keyed_subagent", the default
        print(f"agent session trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {RUN_TO_DONE_INSTRUCTION}"
        )
        r = Registrar.load(registry_url(save_dir))
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
