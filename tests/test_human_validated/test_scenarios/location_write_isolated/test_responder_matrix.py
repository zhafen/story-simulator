"""Coverage matrix: every responder gets its own live regression, instead
of only whichever one an individual scenario test happens to exercise.

Originally a full (driver, responder) grid -- split after the
client_trace_path gap (keyed_subagent's own trace-threading plumbing
shipped fully unit-tested but was never actually driven by a live model;
see start_world_instruction's own docstring) revealed that no test ever
drove every pairing this codebase claims to support. The driver axis
(does each of claude/copilot/mcp_client actually work, and does trace
convergence hold for each) has since moved to emc2p itself
(tests/testing/test_trace_convergence.py), generically, independent of
any downstream project's own tool names -- story-simulator's own matrix
below only needs to prove ITS OWN responder logic is correct, at
whichever single driver each responder actually needs, not re-verify
driver mechanics per driver on top of that.

Uses location_write_isolated (one car, one already-resolvable event)
rather than the fuller parking/race scenarios, since the point here is
combinatorial breadth (every responder, at least once) rather than depth
on any one of them.

Not every responder needs its own driver choice: "subagent" only makes
sense paired with driver="claude" -- it asks the connected host to
delegate to its own isolated subagent mechanism (e.g. Claude Code's
Agent/Task tool), and no such mechanism exists for driver="mcp_client"
(see story_simulator.resolve's own module docstring). "host" and
"keyed_subagent" don't depend on the outer driver having its own subagent
tool, so they use mcp_client, the cheapest/always-available driver in
this environment.
"""

from pathlib import Path

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.agent_session import Driver
from story_simulator.config import registry_url
from test_human_validated.helpers import create_session, start_world_instruction

SCENARIO_DIR = Path(__file__).parent.parent.parent.parent / "data" / "scenarios" / "location_write_isolated"

# (responder, driver) -- see module docstring for why "subagent" is the
# one responder pinned to a specific driver rather than the shared default.
_COMBINATIONS: list[tuple[str, Driver]] = [
    ("host", "mcp_client"),
    ("keyed_subagent", "mcp_client"),
    ("subagent", "claude"),
]


def _skip_reason(driver: Driver) -> str | None:
    """None if `driver` is actually runnable in this environment, else why not."""
    import shutil

    if driver == "claude" and shutil.which("claude") is None:
        return "claude CLI not installed in this environment"
    return None


@pytest.mark.live
@pytest.mark.parametrize("responder,driver", _COMBINATIONS, ids=[f"{r}-{d}" for r, d in _COMBINATIONS])
def test_scenario_resolves_under_every_responder(tmp_path: Path, responder: str, driver: Driver):
    """car_a parks in parking_spot_1 under every supported responder --
    not just whichever one an individual scenario test happens to use.

    For responder="keyed_subagent" specifically, also confirms trace
    convergence (keyed_subagent's own judgment call actually lands in the
    session's trace_path) -- the exact thing that silently never happened
    before start_world_instruction existed. The GENERIC version of this
    check (does convergence hold for every driver) lives in emc2p now;
    this is the story-simulator-specific proof that keyed_subagent's own
    pending_resolution wiring actually uses it correctly.
    """
    reason = _skip_reason(driver)
    if reason:
        pytest.skip(reason)

    save_dir = tmp_path / "test_save"
    with create_session(save_dir, driver=driver, responder=responder, turn_timeout=180, session_timeout=180) as session:
        narration = session.send_turn(start_world_instruction(session, save_dir, SCENARIO_DIR))
        r = Registrar.load(registry_url(save_dir))
        location = r.safe_view_current("location.value", "car_a").to_scalar()
        assert location is not None and "parking_spot_1" in location, (
            f"car_a should be parked in parking_spot_1 -- narration: {narration!r}"
        )

        if responder == "keyed_subagent":
            from emc2p.testing.render_trace import parse_trace

            turns = parse_trace(session.trace_path)
            # keyed_subagent's own nested run_tool_calling_loop call dispatches
            # through REGISTRAR_TOOL_SPECS's bare names ("update_registry"),
            # not the "mcp__story-simulator__"-prefixed names the outer
            # MCP-dispatched call uses -- checking for the bare name is what
            # actually proves the NESTED call's own trace converged here,
            # not just that the outer model happened to also call it.
            tool_calls = [tc for t in turns for tc in t.tool_calls]
            assert any(tc.name == "update_registry" for tc in tool_calls), (
                f"no bare (nested) update_registry call appears anywhere in {session.trace_path} -- "
                "if the scenario still passed, keyed_subagent's own write never made "
                "it into the trace, meaning trace convergence silently failed again"
            )
