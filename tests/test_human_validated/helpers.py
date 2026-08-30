"""Shared infrastructure for live end-to-end tests that drive
story-simulator-mcp through a real MCP client.

`create_session` (the one entry point every live test in this package
should actually call) plus registry-reading helpers, imported by every
sibling test module in this tests/test_human_validated/ package. Carries
no live test of its own: a combined driving+parking scenario resolved as
one event is deliberately not tested here -- that resolves unreliably in
a way the split-events structure
(test_scenarios/parking_split/test_scenario.py) doesn't.

There is no in-process narrator to call directly, so a live test needs a
real client driving this repo's own MCP server -- one of three drivers,
selected via `driver` (see LIVE_TEST_DRIVER_ENV_VAR/DEFAULT_LIVE_TEST_DRIVER
below): `"mcp_client"` (the default) is a real `mcp` client plus
`emc2p.agents.tool_calling_loop` (via litellm) playing the "connected"
side -- works with any litellm-supported model, DeepSeek by default
(DEFAULT_LIVE_TEST_MODEL). `"claude"` spawns `claude -p` as a real
subprocess instead, exactly the way the README's quick-start describes a
client connecting, so it can only ever drive a Claude model -- still used
by `tests/location_write_harness.py` for its own sake (Claude Code's own
CLI/usage-tracking specifically, not just any model). `"copilot"` spawns
the GitHub Copilot CLI the same way, for a Claude/DeepSeek-independent
run using whatever credentials that CLI already has configured -- useful
when a caller has no API key of its own but does have a headless CLI
already signed in. The actual subprocess/client-driving/timeout/trace
mechanics for all three live in `emc2p.testing.agent_session.
create_agent_session` (`emc2p.testing.headless_session.HeadlessSession`/
`emc2p.testing.mcp_client_session.McpClientSession` underneath) --
generic infrastructure with no notion of story-simulator's own MCP tool
names or registry backend; `create_session` just fixes those
project-specific details (this repo's .mcp.json, its
"mcp__story-simulator__*" tool namespace, and the per-save Postgres
schema) so every caller in this test suite constructs a session as
`create_session(save_dir)`.

Written for the current event-entity simulation loop (no character/NPC
module -- see docs/architecture.md and CLAUDE.md's shelving note): world
state is `event` entities, each ready to resolve once world time reaches
its own end_time (start_time + duration), and every such event resolves
via two separate responder calls (resolve, then plan) -- see
`McpClientSession`'s own docstring for which responder answers them by
default here versus what a real deployment defaults to. At
responder="host"/"subagent", the connected agent is expected to decide
each step itself, looking up whatever it needs via view_registry/
view_entity and recording its own decisions via update_registry, exactly
as the server's own tool instructions describe; at responder=
"keyed_subagent", those same tools are what it's given too, just called
in-process rather than by the connected agent over MCP (see
`story_simulator.keyed_subagent`), so the connected agent's own job
narrows to driving `advance_simulation` to "done".
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

# Cheapest available Claude model. Kept deliberately weak rather than
# swapped for a stronger one -- these tools need to hold up under a bad
# model's mistakes. Only meaningful for driver="claude" (a real
# `claude -p` subprocess) -- driver="mcp_client"'s own default lives at
# DEFAULT_LIVE_TEST_MODEL below.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# DeepSeek, matching config.DEFAULT_KEYED_SUBAGENT_MODEL -- any
# litellm-supported model works here (driver="mcp_client" has no CLI to
# be tied to), this is just this suite's own choice of default.
DEFAULT_LIVE_TEST_MODEL = "deepseek/deepseek-chat"

# emc2p.testing.mcp_client_session.McpClientSession's own default (15) is
# a conversational-turn-count budget, not a whole-simulation one -- these
# tests each drive an entire multi-event "run to done" in one open-ended
# send_turn call, needing several tool calls per event per responder step.
# Only meaningful for driver="mcp_client" -- see McpClientSession's own
# docstring for why this can't just stay at the generic default.
DEFAULT_LIVE_TEST_MAX_TOOL_ITERATIONS = 60

# The one MCP tool namespace this repo's own .mcp.json exposes --
# emc2p.testing.agent_session.create_agent_session's underlying drivers
# strip every other built-in tool outright.
_ALLOWED_TOOLS = ["mcp__story-simulator__*"]

# Flips create_session's own default `responder` (see its docstring) for
# every live test that doesn't pin one explicitly.
LIVE_TEST_RESPONDER_ENV_VAR = "STORY_SIM_LIVE_TEST_RESPONDER"
DEFAULT_LIVE_TEST_RESPONDER = "keyed_subagent"

# Flips create_session's own default `driver` for every live test that
# doesn't pin one explicitly -- same resolution order as responder above
# (explicit argument > env var > this default). "mcp_client" stays the
# default since it's the only driver not tied to one specific CLI/model.
LIVE_TEST_DRIVER_ENV_VAR = "STORY_SIM_LIVE_TEST_DRIVER"
DEFAULT_LIVE_TEST_DRIVER: Driver = "mcp_client"

# Only "claude"/"copilot" have one obvious model to default to (their own
# headless CLI's own default flag); "mcp_client" needs an explicit
# litellm model string regardless, so its own entry here is None --
# create_session raises rather than silently picking one for that driver.
_DEFAULT_MODEL_BY_DRIVER: dict[Driver, str | None] = {
    "claude": LOW_QUALITY_MODEL,
    "copilot": None,
    "mcp_client": DEFAULT_LIVE_TEST_MODEL,
}


def _session_extra_env(save_dir: Path, responder: str | None) -> dict[str, str]:
    """The env every driver's spawned server(s) need to see -- the one
    piece of per-session state only this repo can know ahead of time
    (`save_dir`'s own Postgres schema), plus which responder to run with
    (see LIVE_TEST_RESPONDER_ENV_VAR's own docstring above).
    """
    if responder is None:
        responder = os.environ.get(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)
    return {
        # STORY_SIM_HEADLESS_TEST tells this repo's own Stop hooks that this
        # subprocess is automated, not an interactive session a nudge can derail.
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
    """story-simulator's own live-test session factory: fixes
    `emc2p.testing.agent_session.create_agent_session`'s generic
    constructor to this repo's own `.mcp.json`/allowed-tools/cwd/per-save
    extra_env, the same fix-up the two now-removed `HeadlessSession`/
    `McpClientSession` subclasses used to duplicate between themselves
    (see docs/manifest/history.yaml:
    project_history.headless_and_mcp_client_session_unified_into_create_session
    for that removal).

    `driver` picks which of the three underlying session types actually
    runs -- `"claude"`/`"copilot"` spawn that provider's own headless CLI
    as a real subprocess (so each can only ever drive that CLI's own
    model, or whatever model each CLI defaults to); `"mcp_client"` (the
    default) is a real `mcp` client plus `emc2p.agents.tool_calling_loop`
    (via litellm) instead, working with any litellm-supported model --
    DeepSeek by default (see DEFAULT_LIVE_TEST_MODEL) -- for the
    "host"-responder tests exercising the *connected* model's own
    reasoning, not just for keyed_subagent's own already-DeepSeek-by-
    default judgment calls. Resolved the same way as `responder`
    (explicit argument > LIVE_TEST_DRIVER_ENV_VAR > DEFAULT_LIVE_TEST_DRIVER),
    so the whole suite's default can be flipped for one run
    (`STORY_SIM_LIVE_TEST_DRIVER=claude uv run pytest -m live`) without
    editing any test file.

    `model` defaults per-driver (see _DEFAULT_MODEL_BY_DRIVER) --
    "claude" to LOW_QUALITY_MODEL, "mcp_client" to DEFAULT_LIVE_TEST_MODEL.
    "copilot" has no such default (no verified-correct model string for
    that CLI to fall back to), so an explicit `model` is required there.

    `responder` defaults to DEFAULT_LIVE_TEST_RESPONDER ("keyed_subagent"),
    not `config.event_responder()`'s own "host" default -- a test-harness
    default only, set via STORY_SIM_RESPONDER in the spawned subprocess's
    own env, independent of whatever a real deployment's own
    STORY_SIM_RESPONDER is configured to (switching that deployment
    default is separate, currently unstarted work). A caller whose own
    point is exercising the *connected* model's reasoning/MCP-write
    behavior specifically passes `responder="host"` explicitly instead,
    which always wins over the env var regardless: with keyed_subagent as
    responder, resolve/plan judgment calls never reach the connected
    model at all (answered in-process instead), which would silently
    stop testing what those tests each document themselves as testing,
    even though their final-state assertions could still pass.

    `max_tool_iterations` is only meaningful for driver="mcp_client" --
    `create_agent_session` drops it for the other two drivers, whose
    underlying HeadlessSession has no such per-turn tool-call ceiling.
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


# Generic across any scenario -- doesn't name events, components, or
# outcomes, so it's shared rather than duplicated per scenario the way
# _parked_at/_placement-style domain-specific checks are (each scenario's
# own test_scenario.py keeps its own copy of those instead). Deliberately
# doesn't restate advance_simulation's own mechanics (call with neither/
# resume_token+answer args, what "done"/"input_required" mean, ...) --
# that's already this tool's own docstring, which a real connected agent
# reads directly; repeating it here would be the same duplication this
# constant's own extraction was meant to fix, just moved one level down.
# One instruction for every responder (host, subagent, keyed_subagent
# alike): each individual judgment-call prompt advance_simulation raises
# already frames what it needs from whoever answers it (see
# `story_simulator.resolve`'s own module docstring), so the initial
# instruction doesn't need its own responder-specific variant to say it
# again -- just keep calling advance_simulation until done.
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
    """Order evidence, generic across scenarios: each alias in
    `write_order["times"]` should have its own `write_order["component_type"]`
    value time-stamped with the given world time (see
    `core._next_time_stamp`), confirming it was recorded while its own
    event resolved -- not retroactively, and not out of turn relative to
    the other aliases checked alongside it.

    What varies between scenarios is only the data (which component type,
    which alias->time map) -- the check itself doesn't, so this is shared
    rather than reimplemented per scenario/test module.
    """
    component_type = write_order["component_type"]
    expected_times = write_order["times"]
    times = {alias: write_time(registrar, component_type, alias) for alias in expected_times}
    for alias, expected_time in expected_times.items():
        assert times[alias] == pytest.approx(expected_time), (
            f"{alias}'s {component_type} should be recorded at {expected_time} -- got {times}"
        )


