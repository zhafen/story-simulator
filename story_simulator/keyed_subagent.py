"""The "keyed_subagent" event responder: a nested specialist call on
story-simulator's own API key.

Its own registry tool access is dispatched in-process rather than over
MCP (see `story_simulator.resolve`'s module docstring for the full
responder picture -- including the one case, its own time-budget
check-in, where it does still round-trip to the host over MCP -- and
`story_simulator.config.event_responder`/`keyed_subagent_model` for how
it's selected/configured).

The actual tool-calling loop (model completion, tool dispatch, iteration
cap, usage logging), the tool list, and the dispatch-by-name routing
itself all live in emc2p now (`emc2p.agents.tool_calling_loop.
run_tool_calling_loop`/`REGISTRAR_TOOL_SPECS`, `RegistrarSessions.
dispatch`) -- nothing story-simulator-specific about any of it, so none
of it stays duplicated here. This module supplies only what's actually
story-simulator's own: which model answers (`keyed_subagent_model()`),
and this world's already-open `story_simulator.core.registrar_sessions`
instance plus `session` identity, so `dispatch()`'s calls land in-process
(no MCP round-trip, no second subprocess) on this exact world's registrar
rather than a fresh one -- `call_keyed_subagent` already runs inside
story-simulator-mcp's own process.

`mcp_server.py`'s own tools -- start_world/advance_simulation, and
update_registry's preview/confirm_token flow -- are deliberately not
exposed here: keyed_subagent only ever answers one judgment call, it has
no business driving the simulation loop itself, and it has no reviewer of
its own to make a two-round-trip preview/confirm flow meaningful.
"""

from __future__ import annotations

import json
import time as _time
from pathlib import Path
from typing import Any

from emc2p.agents.tool_calling_loop import REGISTRAR_TOOL_SPECS, run_tool_calling_loop

from story_simulator import core
from story_simulator.config import keyed_subagent_model

REPO_ROOT = Path(__file__).parent.parent

# Append-only usage log, not per-session like HeadlessSession's own
# usage.json -- multiple concurrent MCP subprocesses may write here. Gitignored.
USAGE_LOG_PATH = REPO_ROOT / ".keyed_subagent_usage.jsonl"

# TEMPORARY diagnostic instrumentation (#70): logs each update_registry
# call (prompt, prior state, args, result) for post-hoc misfire debugging.
WRITE_TRACE_LOG_PATH = REPO_ROOT / ".write_call_trace.jsonl"


def _log_write_call(record: dict[str, Any]) -> None:
    try:
        with WRITE_TRACE_LOG_PATH.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:  # noqa: BLE001 -- diagnostic-only, never break the actual call
        pass


async def call_keyed_subagent(prompt: str, session: Any) -> str:
    """Answer one already-framed judgment prompt via `keyed_subagent_model()`,
    with real registry access so it can actually persist what it decides.

    Access to view_registry/view_entity/update_registry/consolidate_review,
    not just narrating it.

    `session` is the same MCP session id `core.registrar_sessions` already
    keys its `_registrars`/`_export_dirs` off of -- passed through from
    `TurnReplay.resolve` (see that module) so `dispatch()`'s calls below
    land on this exact world's already-open registrar, not a fresh one.
    """

    def _dispatch(name: str, arguments: dict[str, Any]) -> str:
        if name != "update_registry":
            return core.registrar_sessions.dispatch(session, name, arguments)

        registrar = core.registrar_sessions.get_registrar(session)
        registry_before = registrar.summarize_components()
        record: dict[str, Any] = {
            "timestamp": _time.time(),
            "prompt": prompt,
            "arguments": arguments,
            "registry_before": registry_before,
        }
        try:
            result = core.registrar_sessions.dispatch(session, name, arguments)
        except Exception as exc:  # noqa: BLE001 -- log then let the caller's own handling see it
            record["error"] = str(exc)
            _log_write_call(record)
            raise
        record["result"] = result
        _log_write_call(record)
        return result

    return await run_tool_calling_loop(
        prompt,
        model=keyed_subagent_model(),
        dispatch=_dispatch,
        tools=REGISTRAR_TOOL_SPECS,
        usage_log_path=USAGE_LOG_PATH,
        trace_path=core.registrar_sessions.get_trace_path(session),
        trace_actor="keyed_subagent",
    )
