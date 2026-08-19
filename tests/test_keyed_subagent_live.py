"""Live end-to-end confirmation that "keyed_subagent" (see
story_simulator.keyed_subagent/emc2p.agents.keyed_subagent) actually
resolves a scenario and persists what it decides.

The missing "Test plan" item PR #59/issue #58 both called for and left
unstarted: "Run a live test confirming update_registry calls are
actually persisted by keyed_subagent (save_dir/world/ gets
created/updated)".

Reuses tests/data/scenarios/race (the same fixture
tests/test_race_placement_live.py exercises against the *connected*
model), since its expected finishing order is already known-good -- car_b
first, car_c second, car_a third -- see that test's own docstring for
why. The difference here is who answers each event's resolve/plan
judgment call: HeadlessSession defaults to responder="keyed_subagent"
(see its own docstring), so the connected model's own job narrows to just
driving advance_simulation to "done" -- keyed_subagent (DeepSeek by
default) does the actual reasoning and update_registry writes itself,
in-process, via its own registry tool access.
"""

from pathlib import Path

import pytest

from test_human_validated import HeadlessSession, _event_states, _load_registrar
from emc2p.registrar import Registrar
from emc2p.testing.registry_checks import write_time
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent
RACE_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "race"

# keyed_subagent does the actual resolve/plan reasoning and writes
# in-process -- the connected model's only job is driving it to completion.
_DRIVE_TO_DONE_INSTRUCTION = (
    "Call advance_simulation repeatedly until its status is \"done\". If it ever comes back "
    "with status \"input_required\", just call it again with the same resume_token and a "
    "short answer telling it to keep going -- don't try to answer the substance of any "
    "prompt yourself. Don't narrate anything back to me."
)


def _placement(registrar: Registrar, alias: str) -> int | None:
    """The current `race_placement.value` recorded for an aliased car, or
    None if it has none yet."""
    df = safe_view_current(registrar, "race_placement.value", aliases=alias)
    if df is None or df.empty:
        return None
    return int(df.iloc[-1]["race_placement.value"])


@pytest.mark.live
def test_keyed_subagent_resolves_race_and_persists_to_save_dir(tmp_path):
    """keyed_subagent, not the connected model, must actually do the
    reasoning and recording here.

    Confirmed two ways: (1) the same correctness checks
    test_race_placement_live.py runs against the connected model
    (car_b first, car_c second, car_a third, all three trip events
    complete, each placement time-stamped with its own trip event's
    end_time), and (2) save_dir/world/ actually exists and isn't empty
    afterward -- CLAUDE.md's own re-export-on-every-update_registry
    invariant, which the original bug this responder was built to fix
    (issue #58) violated outright: 50 calls, zero real writes, zero
    save_dir/world/ ever created.
    """
    save_dir = tmp_path / "test_save"

    # Both timeouts raised well past HeadlessSession's own 120s/240s defaults --
    # keyed_subagent's own nested DeepSeek rounds cost real time inside each call.
    with HeadlessSession(save_dir, turn_timeout=420, session_timeout=420) as session:  # responder="keyed_subagent", the new default
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={RACE_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_DRIVE_TO_DONE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _placement(r, "car_b") == 1, (
            f"Car B should be first to actually finish -- narration: {narration!r}"
        )
        assert _placement(r, "car_c") == 2, (
            f"Car C should be second to finish -- narration: {narration!r}"
        )
        assert _placement(r, "car_a") == 3, (
            f"Car A starts first but has the longest trip, so it should actually finish "
            f"last -- narration: {narration!r}"
        )

        states = _event_states(r)
        assert states.get("car_b_trip") == "complete", states
        assert states.get("car_c_trip") == "complete", states
        assert states.get("car_a_trip") == "complete", states

        times = {alias: write_time(r, "race_placement", alias) for alias in ("car_b", "car_c", "car_a")}
        assert times["car_b"] == pytest.approx(1020), (
            f"car_b's race_placement should be recorded at car_b_trip's own end_time -- "
            f"{times}, narration: {narration!r}"
        )
        assert times["car_c"] == pytest.approx(1080), (
            f"car_c's race_placement should be recorded at car_c_trip's own end_time -- "
            f"{times}, narration: {narration!r}"
        )
        assert times["car_a"] == pytest.approx(1800), (
            f"car_a's race_placement should be recorded at car_a_trip's own end_time -- "
            f"{times}, narration: {narration!r}"
        )

        world_dir = save_dir / "world"
        assert world_dir.is_dir(), (
            f"save_dir/world/ was never created -- keyed_subagent's update_registry calls "
            f"never actually persisted anything. narration: {narration!r}"
        )
        assert any(world_dir.iterdir()), f"save_dir/world/ exists but is empty. narration: {narration!r}"
