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

REPO_ROOT = Path(__file__).parent.parent.parent

# Every raw stream-json line from a "claude"/"copilot" driver's subprocess
# lands here, one file per session -- not just the final narrated result.
LIVE_TRACE_DIR = REPO_ROOT / ".live_test_traces"

# Wired into emc2p.testing.live_trial (see conftest.py): how many times
# a live_trial test reruns, and where each trial's CSV row lands.
LIVE_TRIAL_ENV_VAR = "STORY_SIM_LIVE_TRIALS"
LIVE_TRIAL_RESULTS_DIR = REPO_ROOT / ".live_trial_results"

# Cheapest Claude model -- these tools must hold up under a bad model.
# Only used by driver="claude"; mcp_client uses DEFAULT_LIVE_TEST_MODEL.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# Overrides driver="claude"'s own default model (LOW_QUALITY_MODEL) --
# same resolution order as driver/responder above. Not applied to other
# drivers: an mcp_client/copilot model string has different constraints
# (e.g. litellm's own provider-prefixed format), so a bare Claude Code
# CLI model alias set here isn't assumed to be valid for them too.
LIVE_TEST_MODEL_ENV_VAR = "STORY_SIM_LIVE_TEST_MODEL"

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
DEFAULT_LIVE_TEST_RESPONDER = "host"

# Flips create_session's default `driver`; same resolution order as
# responder above. mcp_client is default since it's not CLI/model-tied.
LIVE_TEST_DRIVER_ENV_VAR = "STORY_SIM_LIVE_TEST_DRIVER"
DEFAULT_LIVE_TEST_DRIVER: Driver = "mcp_client"

# "claude" isn't looked up here -- its own resolution (LOW_QUALITY_MODEL,
# overridable via LIVE_TEST_MODEL_ENV_VAR) happens directly in
# create_session. copilot has no obvious default model, so its entry is
# None -- create_session raises rather than silently picking one.
_DEFAULT_MODEL_BY_DRIVER: dict[Driver, str | None] = {
    "copilot": None,
    "mcp_client": DEFAULT_LIVE_TEST_MODEL,
}


def _session_extra_env(
    save_dir: Path, responder: str | None, subagent_time_budget_seconds: float | None
) -> dict[str, str]:
    """Env vars every driver's spawned server needs: save_dir's schema and responder.

    See LIVE_TEST_RESPONDER_ENV_VAR's docstring for responder resolution.
    """
    if responder is None:
        responder = os.environ.get(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)
    env = {
        # Tells this repo's own Stop hooks that this subprocess is
        # automated, not an interactive session a nudge can derail.
        "STORY_SIM_HEADLESS_TEST": "1",
        "IACS_DATABASE_URL": registry_url(save_dir),
        "STORY_SIM_RESPONDER": responder,
    }
    if subagent_time_budget_seconds is not None:
        env["STORY_SIM_SUBAGENT_TIME_BUDGET_SECONDS"] = str(subagent_time_budget_seconds)
    return env


def create_session(
    save_dir: Path,
    *,
    driver: Driver | None = None,
    model: str | None = None,
    responder: str | None = None,
    turn_timeout: float = 240,
    session_timeout: float = 120,
    max_tool_iterations: int = DEFAULT_LIVE_TEST_MAX_TOOL_ITERATIONS,
    subagent_time_budget_seconds: float | None = None,
) -> AgentSession:
    """story-simulator's live-test session factory over create_agent_session.

    `driver`/`model`/`responder` resolve as explicit arg > env var > default.
    `responder` defaults to "host" (the connected driver resolves its own
    judgment calls inline); pass "keyed_subagent" to delegate them to a
    separate in-process model call instead.

    `subagent_time_budget_seconds` overrides
    `STORY_SIM_SUBAGENT_TIME_BUDGET_SECONDS` for this session only
    (default: the 30s production value, sized for a real Claude Code CLI
    session's own tool-call ceiling -- this harness's `mcp_client` driver has none).
    """
    if driver is None:
        driver = os.environ.get(LIVE_TEST_DRIVER_ENV_VAR, DEFAULT_LIVE_TEST_DRIVER)
    if model is None:
        if driver == "claude":
            model = os.environ.get(LIVE_TEST_MODEL_ENV_VAR, LOW_QUALITY_MODEL)
        else:
            model = _DEFAULT_MODEL_BY_DRIVER[driver]
        if model is None:
            raise ValueError(f"driver={driver!r} has no default model -- pass model= explicitly")
    kwargs = dict(
        mcp_config=REPO_ROOT / ".mcp.json",
        allowed_tools=_ALLOWED_TOOLS,
        cwd=REPO_ROOT,
        model=model,
        extra_env=_session_extra_env(save_dir, responder, subagent_time_budget_seconds),
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


def start_world_instruction(session: AgentSession, save_dir: Path, scenario_dir: Path) -> str:
    """The standard opening instruction for a live test: open the world and
    run it to completion.

    Passes this session's own `session.trace_path` as `client_trace_path`
    so a "keyed_subagent" responder's own judgment calls land in the same
    trace file as the rest of this turn (see `start_world`'s own
    `client_trace_path` docstring) -- otherwise nothing tells the
    connected model to supply it, and keyed_subagent's own steps never
    show up in the recorded trace at all.
    """
    return (
        f"Use start_world with save_dir={save_dir}, scenario_dir={scenario_dir}, and "
        f"client_trace_path={session.trace_path} to open a story-simulator world. "
        f"Then {RUN_TO_DONE_INSTRUCTION}"
    )


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
