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

import litellm

from story_simulator.config import keyed_subagent_model


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
    return response.choices[0].message.content or ""
