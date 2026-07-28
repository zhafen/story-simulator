"""Async MCP stdio client wrapper for talking to the iacs MCP server.

Kept separate from world.py so the tool-loop plumbing can be mocked in
non-live unit tests without touching the archivist logic itself.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).parent.parent
IACS_MCP_COMMAND = "uv"
IACS_MCP_ARGS = ["run", "iacs-mcp"]
IACS_MANIFEST_ENV_VAR = "IACS_MANIFEST"


def tool_to_openai_schema(tool: Any) -> dict[str, Any]:
    """Translate an MCP tool listing into an OpenAI-style `tools=[...]` entry.

    LiteLLM normalizes tool calling to this shape across every provider it
    supports, so this is what `story_simulator.agents.run_tool_loop` needs
    for any agent that attaches the iacs MCP server's tools.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


class McpToolSession:
    """An initialized MCP session, with its tools exposed as OpenAI-style schemas."""

    def __init__(self, session: ClientSession, tools: list[dict[str, Any]]):
        self.session = session
        self.tools = tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self.session.call_tool(name, arguments)
        return "\n".join(block.text for block in result.content if block.type == "text")


@asynccontextmanager
async def open_iacs_mcp_session(manifest_dir: str | Path) -> AsyncIterator[McpToolSession]:
    """Spawn the iacs MCP server as a subprocess, pointed at `manifest_dir`."""
    server_params = StdioServerParameters(
        command=IACS_MCP_COMMAND,
        args=IACS_MCP_ARGS,
        env={IACS_MANIFEST_ENV_VAR: str(manifest_dir)},
        cwd=REPO_ROOT,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            # OpenAI-style schemas: what agents.run_tool_loop's LiteLLM calls
            # expect, regardless of which provider a given agent uses.
            tools = [tool_to_openai_schema(t) for t in tools_result.tools]
            yield McpToolSession(session, tools)
