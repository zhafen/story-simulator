"""Shared infrastructure for live end-to-end tests that drive
story-simulator-mcp through a real MCP client.

`HeadlessSession` and registry-reading helpers, imported by every
sibling test module in this tests/test_human_validated/ package.
Carries no live test of its own: the original combined driving+parking
scenario this file used to test (test_car_parking_core_sim) was
removed once it became clear that combined event resolves unreliably
in a way the split-events structure (test_parking_split_live.py)
doesn't -- see docs/manifest/history.yaml:
project_history.combined_parking_test_removed.

There is no in-process narrator to call directly (see
docs/manifest/history.yaml: project_history.turn_pipeline_removed), so
`HeadlessSession` spawns `claude -p` as a real subprocess against this
repo's .mcp.json, exactly the way the README's quick-start describes a
client connecting. The actual subprocess-driving/timeout/trace mechanics
live in `emc2p.testing.headless_session.HeadlessSession` -- generic
infrastructure with no notion of story-simulator's own MCP tool names or
registry backend -- this module's own `HeadlessSession` just fixes those
project-specific details (this repo's .mcp.json, its
"mcp__story-simulator__*"/"mcp__iacs__*" tool namespaces, and the
per-save Postgres schema its sibling iacs-mcp server needs) so every
caller in this test suite can keep constructing it as `HeadlessSession
(save_dir)`, same as before the move.

Written for the current event-entity simulation loop (no character/NPC
module -- see docs/architecture.md and CLAUDE.md's shelving note): world
state is `event` entities, each ready to resolve once world time reaches
its own end_time (start_time + duration), and every such event resolves
via two separate responder calls (resolve, then plan) -- see
`HeadlessSession`'s own docstring for which responder answers them by
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

from emc2p.registrar import Registrar
from emc2p.testing.headless_session import HeadlessSession as _Emc2pHeadlessSession
from emc2p.testing.registry_checks import schema_exists
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent.parent

# Every raw stream-json line from a HeadlessSession's `claude -p` subprocess
# lands here, one file per session -- not just the final narrated result.
LIVE_TRACE_DIR = REPO_ROOT / ".live_test_traces"

# Cheapest available model. Kept deliberately weak rather than swapped for
# a stronger one -- these tools need to hold up under a bad model's mistakes.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# The two MCP tool namespaces this repo's own .mcp.json exposes --
# emc2p.testing.HeadlessSession strips every other built-in tool outright.
_ALLOWED_TOOLS = ["mcp__story-simulator__*", "mcp__iacs__*"]

# Flips HeadlessSession's own default `responder` (see its docstring) for
# every live test that doesn't pin one explicitly.
LIVE_TEST_RESPONDER_ENV_VAR = "STORY_SIM_LIVE_TEST_RESPONDER"
DEFAULT_LIVE_TEST_RESPONDER = "keyed_subagent"


class HeadlessSession(_Emc2pHeadlessSession):
    """story-simulator's own `HeadlessSession`: fixes emc2p's generic
    constructor to this repo's own `.mcp.json`/allowed-tools/cwd.

    Also computes the one piece of per-session state only this repo can
    know ahead of time -- `save_dir`'s own Postgres schema, which the
    sibling iacs-mcp server (also allowed above) needs pointed at
    directly via IACS_DATABASE_URL, or it falls back to its own
    unrelated example manifest, making its tools (list_component_types,
    view_component, ...) useless against this save's actual state --
    exactly the gap that once let a model invent a nonexistent
    component name instead of finding the real `location` schema.

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
    editing any test file. Callers whose own point is exercising the
    *connected* model's reasoning/MCP-write behavior specifically --
    every current caller in this test suite except
    tests/test_race_placement_via_keyed_subagent.py -- pass `responder="host"`
    explicitly instead, which always wins over the env var regardless:
    with keyed_subagent as responder, resolve/plan judgment calls never
    reach the connected model at all (answered in-process instead), which
    would silently stop testing what those tests each document themselves
    as testing, even though their final-state assertions could still pass.
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
        if responder is None:
            responder = os.environ.get(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)
        super().__init__(
            mcp_config=REPO_ROOT / ".mcp.json",
            allowed_tools=_ALLOWED_TOOLS,
            cwd=REPO_ROOT,
            model=model,
            # STORY_SIM_HEADLESS_TEST tells this repo's own Stop hooks that this
            # subprocess is automated, not an interactive session a nudge can derail.
            extra_env={
                "STORY_SIM_HEADLESS_TEST": "1",
                "IACS_DATABASE_URL": registry_url(save_dir),
                "STORY_SIM_RESPONDER": responder,
            },
            trace_dir=LIVE_TRACE_DIR,
            turn_timeout=turn_timeout,
            session_timeout=session_timeout,
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


