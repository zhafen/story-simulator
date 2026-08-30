"""Shared infrastructure for live end-to-end tests driving story-simulator-mcp via a real MCP client.

`create_session` is the one entry point every live test should call.
Three drivers pick which client/model actually connects; see
create_session's own docstring for the resolution order and defaults.
"""

import os
from pathlib import Path

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.agent_session import AgentSession, Driver, create_agent_session
from emc2p.testing.registry_checks import write_time
from story_simulator.config import registry_url
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent.parent

# Every raw stream-json line from a "claude"/"copilot" driver's subprocess
# lands here, one file per session -- not just the final narrated result.
LIVE_TRACE_DIR = REPO_ROOT / ".live_test_traces"

# Cheapest Claude model -- these tools must hold up under a bad model.
# Only used by driver="claude"; mcp_client uses DEFAULT_LIVE_TEST_MODEL.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# DeepSeek, matching config.DEFAULT_KEYED_SUBAGENT_MODEL -- any litellm
# model works for driver="mcp_client"; just this suite's own default.
DEFAULT_LIVE_TEST_MODEL = "deepseek/deepseek-chat"

# McpClientSession's default (15) is a per-turn budget; a whole "run to
# done" needs more tool calls. Only meaningful for driver="mcp_client".
DEFAULT_LIVE_TEST_MAX_TOOL_ITERATIONS = 60

# The one MCP tool namespace this repo's own .mcp.json exposes; other
# built-in tools are stripped by create_agent_session's drivers.
_ALLOWED_TOOLS = ["mcp__story-simulator__*"]

# Flips create_session's own default `responder` (see its docstring) for
# every live test that doesn't pin one explicitly.
LIVE_TEST_RESPONDER_ENV_VAR = "STORY_SIM_LIVE_TEST_RESPONDER"
DEFAULT_LIVE_TEST_RESPONDER = "keyed_subagent"

# Flips create_session's default `driver`; same resolution order as
# responder above. mcp_client is default since it's not CLI/model-tied.
LIVE_TEST_DRIVER_ENV_VAR = "STORY_SIM_LIVE_TEST_DRIVER"
DEFAULT_LIVE_TEST_DRIVER: Driver = "mcp_client"

# mcp_client has no obvious default model, so its entry is None --
# create_session raises rather than silently picking one.
_DEFAULT_MODEL_BY_DRIVER: dict[Driver, str | None] = {
    "claude": LOW_QUALITY_MODEL,
    "copilot": None,
    "mcp_client": DEFAULT_LIVE_TEST_MODEL,
}


def _session_extra_env(save_dir: Path, responder: str | None) -> dict[str, str]:
    """Env vars every driver's spawned server needs: save_dir's schema and responder.

    See LIVE_TEST_RESPONDER_ENV_VAR's docstring for responder resolution.
    """
    if responder is None:
        responder = os.environ.get(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)
    return {
        # Tells this repo's own Stop hooks that this subprocess is
        # automated, not an interactive session a nudge can derail.
        "STORY_SIM_HEADLESS_TEST": "1",
        "IACS_DATABASE_URL": registry_url(save_dir),
        "STORY_SIM_RESPONDER": responder,
    }


def create_session(
    save_dir: Path,
    *,
    driver: Driver | None = None,
    model: str | None = None,
    responder: str | None = None,
    turn_timeout: float = 240,
    session_timeout: float = 120,
    max_tool_iterations: int = DEFAULT_LIVE_TEST_MAX_TOOL_ITERATIONS,
) -> AgentSession:
    """story-simulator's live-test session factory over create_agent_session.

    `driver`/`model`/`responder` resolve as explicit arg > env var > default.
    `responder` defaults to "keyed_subagent"; pass "host" to exercise the
    connected model's own reasoning.
    """
    if driver is None:
        driver = os.environ.get(LIVE_TEST_DRIVER_ENV_VAR, DEFAULT_LIVE_TEST_DRIVER)
    if model is None:
        model = _DEFAULT_MODEL_BY_DRIVER[driver]
        if model is None:
            raise ValueError(f"driver={driver!r} has no default model -- pass model= explicitly")
    kwargs = dict(
        mcp_config=REPO_ROOT / ".mcp.json",
        allowed_tools=_ALLOWED_TOOLS,
        cwd=REPO_ROOT,
        model=model,
        extra_env=_session_extra_env(save_dir, responder),
        trace_dir=LIVE_TRACE_DIR,
        turn_timeout=turn_timeout,
        session_timeout=session_timeout,
    )
    if driver == "mcp_client":
        kwargs["max_tool_iterations"] = max_tool_iterations
    return create_agent_session(driver, **kwargs)


# Generic across scenarios/responders -- doesn't restate
# advance_simulation's own mechanics, already covered by its tool docstring.
RUN_TO_DONE_INSTRUCTION = (
    "Run this scenario to completion via advance_simulation. Don't narrate "
    "anything back to me."
)


def _event_states(registrar: Registrar) -> dict[str, str]:
    """Map of {event_alias: current event_state.value}, or {} if nothing's been recorded yet."""
    df = safe_view_current(registrar, "event_state.value")
    if df is None:
        return {}
    return dict(zip(df["entity_id.alias"], df["event_state.value"]))


def _assert_write_order(registrar: Registrar, write_order: dict) -> None:
    """Asserts each alias's component was time-stamped with its own expected world time.

    Confirms it was recorded while that alias's own event resolved, not
    retroactively or out of turn relative to the others checked alongside it.
    """
    component_type = write_order["component_type"]
    expected_times = write_order["times"]
    times = {alias: write_time(registrar, component_type, alias) for alias in expected_times}
    for alias, expected_time in expected_times.items():
        assert times[alias] == pytest.approx(expected_time), (
            f"{alias}'s {component_type} should be recorded at {expected_time} -- got {times}"
        )
