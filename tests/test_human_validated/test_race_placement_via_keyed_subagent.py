"""Live confirmation that the simulation resolves and persists correctly
when a responder other than the connected model does the resolve/plan
reasoning and the update_registry writes.

Reuses tests/data/scenarios/race (the same fixture
test_scenario_resolution.py's "race" case exercises against the
*connected* model), since its expected finishing order is already
known-good -- car_b first, car_c second, car_a third -- see that
module's own docstring for why. The difference here is who answers each event's resolve/plan
judgment call: McpClientSession defaults to responder="keyed_subagent"
(see its own docstring), so the connected model's own job narrows to just
driving advance_simulation to "done" -- keyed_subagent (DeepSeek by
default) does the actual reasoning and update_registry writes itself,
in-process, via its own registry tool access.

Not a test of keyed_subagent's own tool-calling mechanics (dispatch,
iteration cap, usage logging, ...) -- that lives in emc2p's own
tests/agents/test_tool_calling_loop.py. What this checks is simulation
correctness (does the race still resolve in the right order, with the
right timing) and CLAUDE.md's own re-export-on-every-update_registry
invariant (save_dir/world/ actually gets created/updated), independent
of which responder is doing the driving.
"""

from pathlib import Path

import pytest

from test_human_validated.helpers import (
    McpClientSession,
    _assert_write_order,
    _event_states,
    _load_registrar,
    _placement,
    load_expected,
)
from emc2p.testing.expected_fixtures import assert_subset

REPO_ROOT = Path(__file__).parent.parent.parent
RACE_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "race"

# keyed_subagent does the actual resolve/plan reasoning and writes
# in-process -- the connected model's only job is driving it to completion.
_DRIVE_TO_DONE_INSTRUCTION = (
    "Call advance_simulation repeatedly until its status is \"done\". If it ever comes back "
    "with status \"input_required\", just call it again with the same resume_token and a "
    "short answer telling it to keep going -- don't try to answer the substance of any "
    "prompt yourself. Don't narrate anything back to me."
)


@pytest.mark.live
def test_race_placement_resolves_and_persists_via_keyed_subagent(tmp_path):
    """Does the simulation still resolve correctly, and does the write
    actually persist, when keyed_subagent (not the connected model) is
    doing the resolve/plan reasoning and the update_registry writes?

    Confirmed two ways: (1) the same correctness checks
    test_race_placement_live.py runs against the connected model
    (car_b first, car_c second, car_a third, all three trip events
    complete, each placement time-stamped with its own trip event's
    end_time), and (2) save_dir/world/ actually exists and isn't empty
    afterward -- CLAUDE.md's own re-export-on-every-update_registry
    invariant.
    """
    save_dir = tmp_path / "test_save"

    # Both timeouts raised well past McpClientSession's own 120s/240s defaults --
    # keyed_subagent's own nested DeepSeek rounds cost real time inside each call.
    with McpClientSession(save_dir, turn_timeout=420, session_timeout=420) as session:  # responder="keyed_subagent", the new default
        print(f"McpClientSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={RACE_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_DRIVE_TO_DONE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)
        expected = load_expected("race")

        placements = {alias: _placement(r, alias) for alias in expected.race_placement}
        try:
            assert_subset("race_placement", expected.race_placement, placements)
            assert_subset("event_state", expected.event_state, _event_states(r))
            _assert_write_order(r, expected)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc

        world_dir = save_dir / "world"
        assert world_dir.is_dir(), (
            f"save_dir/world/ was never created -- keyed_subagent's update_registry calls "
            f"never actually persisted anything. narration: {narration!r}"
        )
        assert any(world_dir.iterdir()), f"save_dir/world/ exists but is empty. narration: {narration!r}"
