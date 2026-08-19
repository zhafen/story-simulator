"""The "keyed_subagent" event responder: a nested specialist call on
story-simulator's own API key.

Its own registry tool access is dispatched in-process rather than over
MCP (see `story_simulator.resolve`'s module docstring for the full
responder picture -- including the one case, its own time-budget
check-in, where it does still round-trip to the host over MCP -- and
`story_simulator.config.event_responder`/`keyed_subagent_model` for how
it's selected/configured).

The actual tool-calling loop (model completion, tool dispatch, iteration
cap, usage logging) lives in `emc2p.agents.keyed_subagent` -- nothing
story-simulator-specific about driving an LLM through a sequence of tool
calls until it gives a final answer, so that mechanism moved to emc2p
(alongside `emc2p.testing.headless_session`, extracted from this project
the same way) rather than staying duplicated here. This module supplies
only the story-simulator-specific part: which four tools to expose
(`view_registry`/`view_entity`/`update_registry`/`consolidate_review`,
`emc2p.agents.keyed_subagent.REGISTRAR_TOOL_SPECS`'s own shape) and how to
actually dispatch them -- wired directly to `story_simulator.core`'s own
functions (the exact same ones `mcp_server.py`'s tools delegate to),
called in-process (no MCP round-trip, no second subprocess) since
`call_keyed_subagent` already runs inside story-simulator-mcp's own
process, on the same already-open registrar `session` identifies.

`mcp_server.py`'s own tools -- start_world/advance_simulation, and
update_registry's preview/confirm_token flow -- are deliberately not
exposed here: keyed_subagent only ever answers one judgment call, it has
no business driving the simulation loop itself, and it has no reviewer of
its own to make a two-round-trip preview/confirm flow meaningful (see
#74/#76 for that flow's origin).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emc2p.agents.keyed_subagent import REGISTRAR_TOOL_SPECS, run_tool_calling_loop

from story_simulator import core
from story_simulator.config import keyed_subagent_model

REPO_ROOT = Path(__file__).parent.parent

# Append-only usage log, not per-session like HeadlessSession's own
# usage.json -- multiple concurrent MCP subprocesses may write here. Gitignored.
USAGE_LOG_PATH = REPO_ROOT / ".keyed_subagent_usage.jsonl"


def _dispatch_tool_call(name: str, arguments: dict, session: Any) -> str:
    if name == "view_registry":
        return core.view_registry(session, arguments["component_type"])
    if name == "view_entity":
        return core.view_entity(session, arguments["entity_id"])
    if name == "update_registry":
        return core.update_registry(session, arguments["yaml_string"])
    if name == "consolidate_review":
        return core.consolidate_review(session, arguments.get("limit", 20))
    return f"Error: unknown tool {name!r}"


async def call_keyed_subagent(prompt: str, session: Any) -> str:
    """Answer one already-framed judgment prompt via `keyed_subagent_model()`,
    with real registry access so it can actually persist what it decides.

    Access to view_registry/view_entity/update_registry/consolidate_review,
    not just narrating it.

    `session` is the same MCP session id `core._get_registrar`/
    `_get_save_dir` already key off of -- passed through from
    `TurnReplay.resolve` (see that module) so the tool calls below land on
    this exact world's already-open registrar, not a fresh one.
    """
    return await run_tool_calling_loop(
        prompt,
        model=keyed_subagent_model(),
        dispatch=lambda name, arguments: _dispatch_tool_call(name, arguments, session),
        tools=REGISTRAR_TOOL_SPECS,
        usage_log_path=USAGE_LOG_PATH,
    )
