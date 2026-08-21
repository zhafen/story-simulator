"""Shared infrastructure for live end-to-end tests that drive
story-simulator-mcp through a real MCP client.

`McpClientSession` (the class every live test in this package should
actually construct) plus registry-reading helpers, imported by every
sibling test module in this tests/test_human_validated/ package. Carries
no live test of its own: the original combined driving+parking scenario
this file used to test (test_car_parking_core_sim) was removed once it
became clear that combined event resolves unreliably in a way the
split-events structure (test_parking_split_live.py) doesn't -- see
docs/manifest/history.yaml: project_history.combined_parking_test_removed.

There is no in-process narrator to call directly (see docs/manifest/
history.yaml: project_history.turn_pipeline_removed), so a live test
needs a real MCP client driving this repo's own server. `McpClientSession`
is a real `mcp` client plus `emc2p.agents.tool_calling_loop` (via litellm)
playing the "connected" side -- works with any litellm-supported model,
DeepSeek by default (DEFAULT_LIVE_TEST_MODEL). `HeadlessSession` is the
older alternative, still kept for `tests/location_write_harness.py`'s own
sake (it needs Claude Code's own CLI/usage-tracking specifically, not
just any model): it spawns `claude -p` as a real subprocess instead,
exactly the way the README's quick-start describes a client connecting,
so it can only ever drive a Claude model. The actual subprocess/client-
driving/timeout/trace mechanics for both live in
`emc2p.testing.headless_session.HeadlessSession`/`emc2p.testing.
mcp_client_session.McpClientSession` -- generic infrastructure with no
notion of story-simulator's own MCP tool names or registry backend; this
module's own subclasses just fix those project-specific details (this
repo's .mcp.json, its "mcp__story-simulator__*"/"mcp__iacs__*" tool
namespaces, and the per-save Postgres schema its sibling iacs-mcp server
needs) so every caller in this test suite can keep constructing either as
`McpClientSession(save_dir)`/`HeadlessSession(save_dir)`, same as before
the move.

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

The character-module-era tests that used to live in this file (NPC/move
scenarios, an earlier version of this same class) are preserved at
shelved/tests/test_human_validated.py, dormant until that module is
un-shelved.
"""

import os
from pathlib import Path
from types import ModuleType

from emc2p.registrar import Registrar
from emc2p.testing.expected_fixtures import load_expected_module
from emc2p.testing.headless_session import HeadlessSession as _Emc2pHeadlessSession
from emc2p.testing.mcp_client_session import McpClientSession as _Emc2pMcpClientSession
from emc2p.testing.registry_checks import schema_exists
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent.parent

# Per-scenario known-correct final state (tests/test_human_validated/expected/
# <name>.py), loaded via emc2p's own shared expected-fixtures framework --
# see that module's own docstring for the load/transform/compare-to-expected.py
# contract this package's live tests build their comparisons on. Unlike
# iacs's own use of the same framework, the "transformation" step here is a
# live headless/MCP session's turns, not an in-process Hamilton driver, so
# only `load_expected_module`/`assert_subset` get reused, not
# `ExpectedValueChecker` (which is specific to checking individual Hamilton
# node results as they execute).
EXPECTED_DIR = REPO_ROOT / "tests" / "test_human_validated" / "expected"


def load_expected(name: str) -> ModuleType:
    """Load tests/test_human_validated/expected/<name>.py as a module."""
    return load_expected_module(EXPECTED_DIR / f"{name}.py")

# Every raw stream-json line from a HeadlessSession's `claude -p` subprocess
# lands here, one file per session -- not just the final narrated result.
LIVE_TRACE_DIR = REPO_ROOT / ".live_test_traces"

# Cheapest available model. Kept deliberately weak rather than swapped for
# a stronger one -- these tools need to hold up under a bad model's mistakes.
# Only meaningful for HeadlessSession (a real `claude -p` subprocess) --
# McpClientSession's own default lives at DEFAULT_LIVE_TEST_MODEL below.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# DeepSeek, matching config.DEFAULT_KEYED_SUBAGENT_MODEL -- any
# litellm-supported model works here (McpClientSession has no CLI to be
# tied to), this is just this suite's own choice of default.
DEFAULT_LIVE_TEST_MODEL = "deepseek/deepseek-chat"

# emc2p.testing.mcp_client_session.McpClientSession's own default (15) is
# a conversational-turn-count budget, not a whole-simulation one -- these
# tests each drive an entire multi-event "run to done" in one open-ended
# send_turn call, needing several tool calls per event per responder step.
# See McpClientSession's own docstring below for why this can't just stay
# at the generic default.
DEFAULT_LIVE_TEST_MAX_TOOL_ITERATIONS = 60

# The two MCP tool namespaces this repo's own .mcp.json exposes --
# emc2p.testing.HeadlessSession/McpClientSession strip every other
# built-in tool outright.
_ALLOWED_TOOLS = ["mcp__story-simulator__*", "mcp__iacs__*"]

# Flips HeadlessSession's/McpClientSession's own default `responder` (see
# their docstrings) for every live test that doesn't pin one explicitly.
LIVE_TEST_RESPONDER_ENV_VAR = "STORY_SIM_LIVE_TEST_RESPONDER"
DEFAULT_LIVE_TEST_RESPONDER = "keyed_subagent"


def _session_extra_env(save_dir: Path, responder: str | None) -> dict[str, str]:
    """The env every session subclass below needs its spawned server(s)
    to see -- the one piece of per-session state only this repo can know
    ahead of time (`save_dir`'s own Postgres schema), plus which responder
    to run with (see LIVE_TEST_RESPONDER_ENV_VAR's own docstring above).

    Shared by `HeadlessSession` and `McpClientSession` so the two stay in
    sync automatically rather than by remembering to edit both.
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


class HeadlessSession(_Emc2pHeadlessSession):
    """story-simulator's own `HeadlessSession`: fixes emc2p's generic
    constructor to this repo's own `.mcp.json`/allowed-tools/cwd.

    Only still used by tests/location_write_harness.py, which needs a
    real `claude -p` subprocess specifically (Claude Code's own
    session-usage tracking, and an explicit Sonnet-vs-Haiku model
    comparison) -- every actual `@pytest.mark.live` test in this package
    constructs `McpClientSession` (below) instead, so it isn't limited to
    driving a Claude model. Kept here rather than duplicated into that
    harness script since the two classes still share `_session_extra_env`
    and this same per-save-schema/responder-resolution logic.

    `responder` defaults to DEFAULT_LIVE_TEST_RESPONDER ("keyed_subagent"),
    not `config.event_responder()`'s own "host" default -- a test-harness
    default only, set via STORY_SIM_RESPONDER in the spawned subprocess's
    own env, independent of whatever a real deployment's own
    STORY_SIM_RESPONDER is configured to (switching that deployment
    default is separate, currently unstarted work). Read from
    LIVE_TEST_RESPONDER_ENV_VAR (STORY_SIM_LIVE_TEST_RESPONDER) at
    construction time when not passed explicitly, so the whole suite's
    default can be flipped for one run
    (`STORY_SIM_LIVE_TEST_RESPONDER=host uv run pytest -m live`) without
    editing any test file. A caller whose own point is exercising the
    *connected* model's reasoning/MCP-write behavior specifically passes
    `responder="host"` explicitly instead, which always wins over the env
    var regardless: with keyed_subagent as responder, resolve/plan
    judgment calls never reach the connected model at all (answered
    in-process instead), which would silently stop testing what those
    tests each document themselves as testing, even though their
    final-state assertions could still pass.
    """

    def __init__(
        self,
        save_dir: Path,
        *,
        model: str = LOW_QUALITY_MODEL,
        responder: str | None = None,
        turn_timeout: float = 240,
        session_timeout: float = 120,
    ):
        self.save_dir = save_dir
        super().__init__(
            mcp_config=REPO_ROOT / ".mcp.json",
            allowed_tools=_ALLOWED_TOOLS,
            cwd=REPO_ROOT,
            model=model,
            extra_env=_session_extra_env(save_dir, responder),
            trace_dir=LIVE_TRACE_DIR,
            turn_timeout=turn_timeout,
            session_timeout=session_timeout,
        )


class McpClientSession(_Emc2pMcpClientSession):
    """story-simulator's own `McpClientSession`: the live-test session
    class every test in this package should actually construct.

    Same fix-up `HeadlessSession` above does (this repo's own
    `.mcp.json`/allowed-tools/cwd/per-save extra_env), over
    `emc2p.testing.mcp_client_session.McpClientSession` instead of
    `emc2p.testing.headless_session.HeadlessSession` -- a real MCP client
    plus `emc2p.agents.tool_calling_loop` (via litellm) driving the
    "connected" side, rather than shelling out to the `claude` CLI. That
    difference is what actually matters here: `HeadlessSession` can only
    ever drive a Claude model (it *is* `claude -p`), while this class
    works with any litellm-supported model -- DeepSeek by default (see
    DEFAULT_LIVE_TEST_MODEL) -- for the "host"-responder tests exercising
    the *connected* model's own reasoning, not just for
    keyed_subagent's own already-DeepSeek-by-default judgment calls.
    Same public shape either way (context manager, `send_turn`,
    `usage_summary`, `trace_path`, `turn_timeout`/`session_timeout`), so
    every test that used to construct `HeadlessSession(save_dir, ...)`
    only needs the class name swapped -- with one gap: `claude -p` has no
    fixed per-turn tool-call ceiling the way `run_tool_calling_loop`'s own
    `max_iterations` (McpClientSession's `max_tool_iterations`) does.
    Confirmed live that its own default (15) is too low for one of these
    tests' single open-ended "run everything to done" turn -- a
    six-event scenario needs on the order of 2-4 tool calls per event per
    responder step (resolve, then plan), i.e. well past 15 total -- so
    this subclass raises the default substantially rather than silently
    truncating a still-in-progress turn (the model's last tool call
    simply never runs, with no error surfaced, once the cap is hit).
    """

    def __init__(
        self,
        save_dir: Path,
        *,
        model: str = DEFAULT_LIVE_TEST_MODEL,
        responder: str | None = None,
        turn_timeout: float = 240,
        session_timeout: float = 120,
        max_tool_iterations: int = DEFAULT_LIVE_TEST_MAX_TOOL_ITERATIONS,
    ):
        self.save_dir = save_dir
        super().__init__(
            mcp_config=REPO_ROOT / ".mcp.json",
            allowed_tools=_ALLOWED_TOOLS,
            cwd=REPO_ROOT,
            model=model,
            extra_env=_session_extra_env(save_dir, responder),
            trace_dir=LIVE_TRACE_DIR,
            turn_timeout=turn_timeout,
            session_timeout=session_timeout,
            max_tool_iterations=max_tool_iterations,
        )


def _load_registrar(save_dir: Path, narration: str) -> Registrar:
    """Confirm `save_dir`'s schema actually exists, then load it.

    A weak model can narrate a plausible-sounding scene without ever
    calling `start_world` -- or call it with a subtly wrong `save_dir` it
    mistyped out of the prompt's text, confirmed happening in practice --
    so this checks the schema was actually created for the exact `save_dir`
    the test used before reading it, rather than either silently reading
    whichever schema the connection falls through to when the named one
    doesn't exist (see `config.registry_url`'s docstring) or hitting a
    confusing raw `ibis` error partway through `Registry.from_database`'s
    table enumeration.
    """
    schema = registry_schema_name(save_dir)
    assert schema_exists(resolve_database_dsn(), schema), (
        f"No registry schema exists for {save_dir} -- start_world was not "
        f"actually called for this exact save_dir despite this "
        f"narration: {narration!r}"
    )
    return Registrar.load(registry_url(save_dir))


def _parked_at(location: str | None, spot: str) -> bool:
    """Loosely checks a recorded `location` value names `spot` (e.g.
    "parking_spot_1" or "street"), not any one exact phrasing.

    `location`'s own schema (manifest/builtins.yaml) calls it a "short
    freeform phrase", and confirmed live that a model's correct answer
    can reasonably come out phrased several ways ("parked in
    parking_spot_1" vs. just "parking_spot_1") -- the model shouldn't
    have to guess the one exact wording a test hardcodes. Takes the
    value directly (e.g. from `registrar.get_current_value("location",
    alias=alias)`) rather than reading it itself.
    """
    return location is not None and spot in location


def _placement(registrar: Registrar, alias: str) -> int | str | None:
    """The current `race_placement.value` recorded for an aliased car, or
    None if it has none yet.

    Returns the raw recorded value uncoerced if it isn't int-like (e.g.
    a misfire that wrote "1st" instead of 1) so a failing assertion
    shows what was actually written instead of crashing on a bare `int()` conversion.
    """
    value = registrar.get_current_value("race_placement", "value", alias)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _event_states(registrar: Registrar) -> dict[str, str]:
    """Map of {event_alias: current event_state.value}, or {} if nothing's been recorded yet."""
    df = safe_view_current(registrar, "event_state.value")
    if df is None:
        return {}
    return dict(zip(df["entity_id.alias"], df["event_state.value"]))


