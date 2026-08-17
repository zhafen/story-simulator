"""The "keyed_subagent" responder's actual model call (see
`story_simulator.resolve`'s module docstring for the four-responder
picture, and `story_simulator.config.event_responder`/
`keyed_subagent_model` for how it's selected/configured).

A real tool-calling loop, not a single completion: `resolve_event`'s/
`plan_events`'s own prompts explicitly require the responder to persist
what it decides via `update_registry` itself, not just narrate it for
someone else to write later (see `resolve_event`'s own docstring --
"persisting is entirely the responder's own, not a return value this
code applies on its behalf"). A bare text completion (this module's
original form) could never actually do that: confirmed live, 50 calls in
a single run, zero `update_registry` calls, zero recorded progress --
`event_state` never advanced, so the same event(s) just kept getting
popped and re-asked until the time budget ran out.

Tool access is wired directly to `story_simulator.core`'s own functions
(`view_registry`/`view_entity`/`update_registry`/`consolidate_review` --
the exact same ones `mcp_server.py`'s tools delegate to), not through a
separate MCP client/subprocess: `call_keyed_subagent` already runs
in-process, inside story-simulator-mcp's own server, on the same already-
open registrar `session` identifies -- no MCP round-trip, no second
subprocess, is needed to reach it.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import litellm

from story_simulator import core
from story_simulator.config import keyed_subagent_model

REPO_ROOT = Path(__file__).parent.parent

# Append-only usage log, not per-session like HeadlessSession's own
# usage.json: call_keyed_subagent has no session concept of its own (it's
# called once per judgment request, however many times a turn needs one),
# and multiple concurrent MCP server subprocesses (one per HeadlessSession)
# may all be writing here -- single-line append writes are atomic enough
# for that on a local filesystem. A caller wanting "usage since my run
# started" filters records by their own `timestamp` rather than relying on
# file position or a session boundary. Gitignored, like `.live_test_traces/`.
USAGE_LOG_PATH = REPO_ROOT / ".keyed_subagent_usage.jsonl"

# Independent of TurnReplay.deadline's wall-clock budget: a safety net
# against a pointless tool-call loop that happens to stay fast per-call
# (so the time budget alone wouldn't catch it) but never converges.
_MAX_TOOL_ITERATIONS = 15

# Mirrors mcp_server.py's own tool set, minus start_world/advance_simulation
# (keyed_subagent only ever answers one judgment call -- it has no business
# driving the simulation loop itself) and update_registry's preview/
# confirm_token flow (a two-round-trip UX feature for a host reviewing its
# own draft before committing; keyed_subagent has no such reviewer -- see
# #74/#76 for that flow's origin).
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "view_registry",
            "description": (
                "View all recorded data for one component type (e.g. "
                '"position", "object", "event_state").'
            ),
            "parameters": {
                "type": "object",
                "properties": {"component_type": {"type": "string"}},
                "required": ["component_type"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_entity",
            "description": "Return every recorded component instance for a specific entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entity hash, alias, or unambiguous path fragment.",
                    }
                },
                "required": ["entity_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_registry",
            "description": (
                "Merge entity-first YAML into the world registry. Each component needs a "
                "leading `- ` list item to attach to an existing aliased entity, e.g. "
                '"car_a:\\n    - event_state:\\n        value: complete". A bare mapping '
                "(no leading `- `) is silently accepted but records nothing at all."
            ),
            "parameters": {
                "type": "object",
                "properties": {"yaml_string": {"type": "string"}},
                "required": ["yaml_string"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consolidate_review",
            "description": (
                "Show every component type recorded in this world so far, to review and "
                "consolidate before finishing."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


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
    with real registry access (view_registry/view_entity/update_registry/
    consolidate_review) so it can actually persist what it decides, not
    just narrate it.

    `session` is the same MCP session id `core._get_registrar`/
    `_get_save_dir` already key off of -- passed through from
    `TurnReplay.resolve` (see that module) so the tool calls below land on
    this exact world's already-open registrar, not a fresh one.
    """
    messages: list[dict] = [{"role": "user", "content": prompt}]
    response = await litellm.acompletion(model=keyed_subagent_model(), messages=messages, tools=_TOOLS)
    _log_usage(response)

    for _ in range(_MAX_TOOL_ITERATIONS):
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        tool_calls = message.tool_calls
        if not tool_calls:
            return message.content or ""
        for tool_call in tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = _dispatch_tool_call(tool_call.function.name, arguments, session)
            except Exception as exc:  # noqa: BLE001 -- feed the error back, don't crash the turn
                result = f"Error: {exc}"
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(result)})
        response = await litellm.acompletion(model=keyed_subagent_model(), messages=messages, tools=_TOOLS)
        _log_usage(response)

    # Ran out of iterations without a final text answer -- return whatever
    # came back from the last call rather than looping forever (the
    # per-call wall-clock budget in TurnReplay.resolve is the primary
    # guard against this; this is a secondary, call-count-based backstop).
    return response.choices[0].message.content or ""


def _log_usage(response) -> None:
    """Best-effort append of this call's cost/tokens to USAGE_LOG_PATH.

    Never lets a logging failure take down the actual judgment call --
    this is auxiliary instrumentation, not something a turn's correctness
    should ever hinge on.
    """
    try:
        usage = getattr(response, "usage", None)
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = None
        record = {
            "timestamp": time.time(),
            "model": response.model,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "cost_usd": cost,
        }
        with USAGE_LOG_PATH.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see docstring
        print(f"[keyed_subagent] could not log usage: {exc}", file=sys.stderr)
