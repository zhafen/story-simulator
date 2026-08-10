"""Provider-agnostic agent configuration and execution, via LiteLLM.

`AgentSpec` is loaded from a `*.yaml` file sitting next to this package
(`npc.yaml`, `terrain.yaml`, ...). Routing every model call through
LiteLLM instead of a provider-specific SDK is what lets `model:` name any
LiteLLM-supported provider, not just Anthropic. Tool schemas aren't part
of `AgentSpec` -- the MCP server builds those itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import litellm
import yaml

DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_TOOL_TURNS = 8


@dataclass
class AgentSpec:
    """An agent's provider-agnostic configuration: who it is, what it knows."""

    name: str
    model: str
    system: str
    description: str = ""

    @classmethod
    def from_yaml(cls, config_path: Path, fallback_system_path: Path | None = None) -> "AgentSpec":
        """Load an AgentSpec from a config YAML, inheriting `system` from `fallback_system_path` if omitted.

        Lets a config that wants another's system prompt omit it entirely
        rather than repeating it.
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
        )


def complete(
    spec: AgentSpec,
    messages: list[dict],
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> Any:
    """Run one LiteLLM completion turn for `spec`, with its system prompt prepended.

    Returns the raw LiteLLM `ModelResponse` rather than unwrapping it,
    since callers need different parts of it (`run_tool_loop` needs
    `tool_calls`; a single-turn caller like `TerrainAgent` only needs
    `.message.content`).
    """
    # LiteLLM/OpenAI-style calls carry the system prompt in `messages`,
    # unlike the Anthropic SDK's separate `system=` kwarg.
    full_messages = [{"role": "system", "content": spec.system}, *messages]
    # `tools=None` (not `[]`) when there are none: some providers reject
    # an empty tools list.
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

    Provider-agnostic since LiteLLM normalizes tool calling to the OpenAI
    shape across every provider it supports.

    `dispatch` is expected to convert an exception into an `"Error: {e}"`
    string result rather than raising: a malformed tool call (bad
    arguments, an unknown name) shouldn't crash the turn, just give the
    model something readable to retry from.
    """
    # Copy so this loop's own appends don't mutate the caller's list.
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

    # max_turns exhausted -- return whatever text came back rather than
    # looping forever.
    return response.choices[0].message.content or ""
