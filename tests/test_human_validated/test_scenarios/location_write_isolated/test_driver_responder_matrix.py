"""Coverage matrix: every valid (driver, responder) combination gets its
own live regression, instead of only whichever pairing an individual
scenario test happens to exercise.

Split out after the client_trace_path gap (issue: keyed_subagent's own
trace-threading plumbing shipped fully unit-tested but was never actually
driven by a live model -- see start_world_instruction's own docstring):
that gap existed specifically because no test ever drove every
(driver, responder) pairing this codebase claims to support, only the
ones individual scenario tests happened to reach for. Uses
location_write_isolated (one car, one already-resolvable event) rather
than the fuller parking/race scenarios, since the point here is combinatorial
breadth (every pairing, at least once) rather than depth on any one of them.

Not a full 3x3 grid: "subagent" only makes sense paired with
driver="claude" -- it asks the connected host to delegate to its own
isolated subagent mechanism (e.g. Claude Code's Agent/Task tool), and no
such mechanism exists for driver="copilot"/"mcp_client" (see
story_simulator.resolve's own module docstring). "host" and
"keyed_subagent" are meaningful for every driver, since neither depends
on the outer driver having its own subagent tool.
"""

from pathlib import Path

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.agent_session import Driver
from story_simulator.config import registry_url
from test_human_validated.helpers import LOW_QUALITY_MODEL, create_session, start_world_instruction

SCENARIO_DIR = Path(__file__).parent.parent.parent.parent / "data" / "scenarios" / "location_write_isolated"

# (driver, responder, model) -- model is only needed for drivers with no
# built-in default (see helpers._DEFAULT_MODEL_BY_DRIVER); None defers to it.
_COMBINATIONS: list[tuple[Driver, str, str | None]] = [
    ("claude", "host", None),
    ("claude", "subagent", None),
    ("claude", "keyed_subagent", None),
    ("mcp_client", "host", None),
    ("mcp_client", "keyed_subagent", None),
    ("copilot", "host", "gpt-4.1"),
    ("copilot", "keyed_subagent", "gpt-4.1"),
]


def _skip_reason(driver: Driver) -> str | None:
    """None if `driver` is actually runnable in this environment, else why not."""
    import shutil

    if driver == "copilot" and shutil.which("copilot") is None:
        return "copilot CLI not installed/configured in this environment"
    if driver == "claude" and shutil.which("claude") is None:
        return "claude CLI not installed in this environment"
    return None


@pytest.mark.live
@pytest.mark.parametrize(
    "driver,responder,model",
    _COMBINATIONS,
    ids=[f"{d}-{r}" for d, r, _ in _COMBINATIONS],
)
def test_scenario_resolves_under_every_driver_responder_combination(
    tmp_path: Path, driver: Driver, responder: str, model: str | None
):
    """car_a parks in parking_spot_1 under every supported (driver,
    responder) pairing -- not just whichever one an individual scenario
    test happens to use.

    For responder="keyed_subagent" specifically, also confirms trace
    convergence (keyed_subagent's own judgment call actually lands in the
    session's trace_path) -- the exact thing that silently never happened
    before start_world_instruction existed.
    """
    reason = _skip_reason(driver)
    if reason:
        pytest.skip(reason)

    save_dir = tmp_path / "test_save"
    with create_session(
        save_dir, driver=driver, model=model, responder=responder, turn_timeout=180, session_timeout=180
    ) as session:
        narration = session.send_turn(start_world_instruction(session, save_dir, SCENARIO_DIR))
        r = Registrar.load(registry_url(save_dir))
        location = r.get_current_value("location", alias="car_a")
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
