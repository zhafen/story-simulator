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
        local = yaml.safe_load(config_path.read_text())
        system = local.get("system")
        if not system and fallback_system_path is not None:
            system = yaml.safe_load(fallback_system_path.read_text())["system"]
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
    full_messages = [{"role": "system", "content": spec.system}, *messages]
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
    messages = list(initial_messages)
    response = complete(spec, messages, tools=tools, api_key=api_key)
    for _ in range(max_turns):
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if response.choices[0].finish_reason != "tool_calls" or not message.tool_calls:
            return message.content or ""
        for tool_call in message.tool_calls:
            arguments = json.loads(tool_call.function.arguments or "{}")
            result_text = await dispatch(tool_call.function.name, arguments)
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result_text}
            )
        response = complete(spec, messages, tools=tools, api_key=api_key)
    return response.choices[0].message.content or ""
