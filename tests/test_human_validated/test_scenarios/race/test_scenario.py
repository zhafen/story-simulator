"""Live regressions for this directory's scenario.yaml: three cars race for placement.

test_resolves_correctly runs under the default (keyed_subagent) responder
and checks final state; test_persists_via_keyed_subagent is a minimal
sibling that only confirms keyed_subagent's writes actually reach disk --
its update_registry calls go through a different, nested-subagent path
than a host responder's direct tool calls, so persistence isn't a given
the way it is for every other live test.
"""

from pathlib import Path

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.expected_fixtures import assert_subset
from story_simulator.config import registry_url
from test_human_validated.helpers import (
    create_session,
    start_world_instruction,
    _assert_write_order,
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

# Order evidence: each race_placement write should be time-stamped with
# its own trip event's end_time, confirming it wasn't recorded out of turn.
EXPECTED_WRITE_ORDER = {
    "component_type": "race_placement",
    "times": {"car_b": 1020, "car_c": 1080, "car_a": 1800},
}


@pytest.mark.live
def test_resolves_correctly(tmp_path: Path, live_trial):
    """Runs to completion under a live session, then checks final state."""
    save_dir = tmp_path / "test_save"

    with create_session(save_dir, turn_timeout=420, session_timeout=420) as session:  # responder="keyed_subagent", the default
        print(f"agent session trace: {session.trace_path}")
        live_trial.id = str(session.trace_path)
        narration = session.send_turn(start_world_instruction(session, save_dir, SCENARIO_DIR))
        r = Registrar.load(registry_url(save_dir))
        try:
            placements = {
                alias: r.safe_view_current("race_placement.value", alias).to_scalar()
                for alias in EXPECTED_RACE_PLACEMENT
            }
            assert_subset("race_placement", EXPECTED_RACE_PLACEMENT, placements)
            event_states = {
                alias: r.safe_view_current("event_state.value", alias).to_scalar()
                for alias in EXPECTED_EVENT_STATE
            }
            assert_subset("event_state", EXPECTED_EVENT_STATE, event_states)
            _assert_write_order(r, EXPECTED_WRITE_ORDER)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc


@pytest.mark.live
def test_persists_via_keyed_subagent(tmp_path: Path, live_trial):
    """Confirms keyed_subagent's writes reach disk -- see module docstring."""
    save_dir = tmp_path / "test_save"

    with create_session(
        save_dir, responder="keyed_subagent", turn_timeout=420, session_timeout=420
    ) as session:
        print(f"agent session trace: {session.trace_path}")
        live_trial.id = str(session.trace_path)
        narration = session.send_turn(start_world_instruction(session, save_dir, SCENARIO_DIR))
        world_dir = save_dir / "world"
        assert world_dir.is_dir(), (
            f"save_dir/world/ was never created -- keyed_subagent's update_registry calls "
            f"never actually persisted anything. narration: {narration!r}"
        )
        assert any(world_dir.iterdir()), f"save_dir/world/ exists but is empty. narration: {narration!r}"
