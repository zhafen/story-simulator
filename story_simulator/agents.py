"""Provider-agnostic agent configuration and execution, via LiteLLM.

`AgentSpec` is the interchange format between "where an agent's config comes
from" and "how it's run" — today every spec is loaded from a `*.yaml` file
sitting next to this package (`resolver.yaml`, `npc.yaml`, ...), the same
files System classes in `story_simulator.systems` already read directly.
Routing every agent's model call through `complete`/`run_tool_loop` instead
of a provider-specific SDK (previously `anthropic.Anthropic(...)` calls
scattered across `systems.py`) is what lets an agent's `model:` field name
any LiteLLM-supported provider, not just Anthropic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import litellm
import yaml

DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_TOOL_TURNS = 8


@dataclass
class AgentSpec:
    """An agent's provider-agnostic configuration: who it is, what it knows, what it can call.

    `tools` holds tool *names* (resolved against `story_simulator.tools`'s
    registry, or the `"iacs_mcp"` sentinel meaning "attach every tool the
    iacs MCP server exposes") rather than provider-specific tool schemas, so
    a spec stays serializable independent of how its tools end up wired.
    """

    name: str
    model: str
    system: str
    description: str = ""
    tools: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, config_path: Path, fallback_system_path: Path | None = None) -> "AgentSpec":
        """Load an AgentSpec from a config YAML, inheriting `system` from `fallback_system_path` if omitted.

        Mirrors the "test config inherits the prod system prompt" behavior
        `ResolverAgentSystem._load_config`/`AgentWorld._load_config` already
        implement, so `*.test.yaml` variants (e.g. `resolver.test.yaml`) can
        keep overriding just `model`/`name` without repeating the prompt.
        """
        # Step 1: read this agent's own config file.
        local = yaml.safe_load(config_path.read_text())
        # Step 2: if it has no system prompt of its own, borrow one from the
        # fallback config (e.g. a *.test.yaml pulling resolver.yaml's prompt).
        system = local.get("system")
        if not system and fallback_system_path is not None:
            system = yaml.safe_load(fallback_system_path.read_text())["system"]
        # Step 3: build the spec, defaulting optional fields that a minimal
        # config file might omit.
        return cls(
            name=local["name"],
            model=local["model"],
            system=system or "",
            description=local.get("description", ""),
            tools=local.get("tools", []),
        )


def complete(
    spec: AgentSpec,
    messages: list[dict],
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> Any:
    """Run one LiteLLM completion turn for `spec`, with its system prompt prepended.

    Returns the raw LiteLLM `ModelResponse` (OpenAI-shaped: `.choices[0].message`,
    `.choices[0].finish_reason`) rather than unwrapping it here, since callers
    need different parts of it (`run_tool_loop` needs `tool_calls` and
    `finish_reason`; a plain single-turn caller like `TerrainAgent` only
    needs `.choices[0].message.content`).
    """
    # Step 1: put the agent's own system prompt as the first message —
    # LiteLLM/OpenAI-style calls carry it in `messages`, unlike the
    # Anthropic SDK's separate `system=` kwarg.
    full_messages = [{"role": "system", "content": spec.system}, *messages]
    # Step 2: make the actual provider call. `tools=None` (not `[]`) when
    # there are none, since some providers reject an empty tools list.
    return litellm.completion(
        model=spec.model,
        messages=full_messages,
        tools=tools or None,
        max_tokens=DEFAULT_MAX_TOKENS,
        api_key=api_key,
    )


async def run_tool_loop(
    spec: AgentSpec,
    initial_messages: list[dict],
    tools: list[dict],
    dispatch: Callable[[str, dict], Awaitable[str]],
    max_turns: int = DEFAULT_MAX_TOOL_TURNS,
    api_key: str | None = None,
) -> str:
    """Run a multi-turn tool-calling loop for `spec`, returning the final assistant text.

    Generalizes `ArchivistAgentSystem`'s hand-rolled loop (previously tied to
    `anthropic.Anthropic().messages.create`'s Anthropic-specific content-block
    shape) into a provider-agnostic one, since LiteLLM normalizes tool
    calling to the OpenAI shape across every provider it supports: a
    response's `message.tool_calls` (each with `.id`, `.function.name`,
    `.function.arguments` as a JSON string) instead of Anthropic's
    `tool_use` content blocks, and a tool's result goes back as its own
    `{"role": "tool", "tool_call_id": ..., "content": ...}` message instead
    of a `tool_result` block nested in a `user` message.

    `dispatch` converts an exception into an `"Error: {e}"` string result
    rather than raising, the same contract `ArchivistAgentSystem._dispatch_tool`
    already documents: a malformed tool call from the model (bad arguments,
    an unknown name) shouldn't crash the turn, just give the model something
    readable to retry from.
    """
    # Step 1: copy the caller's messages so this loop's own appends don't
    # mutate whatever list they passed in, and make the first model call.
    messages = list(initial_messages)
    response = complete(spec, messages, tools=tools, api_key=api_key)

    for _ in range(max_turns):
        # Step 2: record the model's turn (including any tool_calls) in the
        # transcript before deciding what to do with it.
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        # Step 3: no tool call requested — the model is done, so return its
        # text as the loop's final result.
        if response.choices[0].finish_reason != "tool_calls" or not message.tool_calls:
            return message.content or ""

        # Step 4: otherwise, run every requested tool call and feed each
        # result back as its own "tool" message, keyed to the call that
        # asked for it.
        for tool_call in message.tool_calls:
            arguments = json.loads(tool_call.function.arguments or "{}")
            result_text = await dispatch(tool_call.function.name, arguments)
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result_text}
            )

        # Step 5: give the model another turn to react to those results.
        response = complete(spec, messages, tools=tools, api_key=api_key)

    # Step 6: max_turns exhausted without the model settling on a final
    # answer — return whatever text (if any) came back from the last call
    # rather than looping forever.
    return response.choices[0].message.content or ""
