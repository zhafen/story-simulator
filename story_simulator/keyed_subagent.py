"""The "keyed_subagent" responder's actual model call (see
`story_simulator.resolve`'s module docstring for the four-responder
picture, and `story_simulator.config.event_responder`/
`keyed_subagent_model` for how it's selected/configured).

A revival of the removed `keyed_subagent`/`story_simulator.agents`
mechanism (see resolve.py's docstring and git history), but deliberately
smaller: no `AgentSpec`/YAML config loading, no NPC/character framing --
just LiteLLM routing to whichever model `keyed_subagent_model()` names
(DeepSeek by default, see #89), so any provider LiteLLM supports can
answer a judgment call directly, in-process, without an MCP round-trip to
the host.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import litellm

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


async def call_keyed_subagent(prompt: str) -> str:
    """Answer one already-framed judgment prompt via `keyed_subagent_model()`.

    A single completion, not a tool-calling loop: a judgment call is "what
    happened"/"what's next" narration text, not something that itself
    invokes MCP tools -- `resolve_event`/`plan_events` do the actual
    registry writes afterward based on this text, exactly as they would
    with a "host" or "subagent" answer.
    """
    response = await litellm.acompletion(
        model=keyed_subagent_model(),
        messages=[{"role": "user", "content": prompt}],
    )
    _log_usage(response)
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
