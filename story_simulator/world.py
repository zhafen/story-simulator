import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import yaml
from iacs.architect import Architect

from story_simulator.config import ENVIRONMENT_ID, PROD_AGENT_ID, resolve_anthropic_api_key
from story_simulator.mcp_client import open_iacs_mcp_session

PROD_AGENT_CONFIG_PATH = Path(__file__).parent / "agent.yaml"
TEST_AGENT_CONFIG_PATH = Path(__file__).parent / "agent.test.yaml"
PROD_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.yaml"
TEST_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.test.yaml"

WORLD_YAML_FILENAME = "world.yaml"
MAX_ARCHIVIST_TOOL_TURNS = 8


class World(ABC):
    @abstractmethod
    def respond(self, text: str) -> str:
        raise NotImplementedError


class MirrorWorld(World):
    def respond(self, text: str) -> str:
        return text


class AgentWorld(World):
    def __init__(
        self,
        agent_id: str = PROD_AGENT_ID,
        environment_id: str = ENVIRONMENT_ID,
        config_path: Path = PROD_AGENT_CONFIG_PATH,
    ):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        self.agent_id = agent_id
        self.environment_id = environment_id
        self.config_path = config_path
        self.session_id = None

    def _load_config(self) -> dict:
        local = yaml.safe_load(self.config_path.read_text())
        if not local.get("system"):
            local["system"] = yaml.safe_load(PROD_AGENT_CONFIG_PATH.read_text())["system"]
        return local

    def _sync_agent(self) -> None:
        local = self._load_config()
        current = self.client.beta.agents.retrieve(self.agent_id)
        self.client.beta.agents.update(
            self.agent_id,
            version=current.version,
            name=local["name"],
            description=local.get("description", ""),
            model=local["model"],
            system=local.get("system"),
            tools=local.get("tools", []),
        )

    def _start_session(self) -> None:
        self._sync_agent()
        session = self.client.beta.sessions.create(
            agent=self.agent_id,
            environment_id=self.environment_id,
        )
        self.session_id = session.id
        print(f"Session: https://platform.claude.com/workspaces/default/sessions/{session.id}")

    def respond(self, text: str) -> str:
        if self.session_id is None:
            self._start_session()
        with self.client.beta.sessions.events.stream(session_id=self.session_id) as stream:
            self.client.beta.sessions.events.send(
                session_id=self.session_id,
                events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
            )
            return self._drain(stream)

    def _drain(self, stream) -> str:
        text_parts = []
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        text_parts.append(block.text)
            elif event.type == "session.status_terminated":
                break
            elif event.type == "session.status_idle":
                if event.stop_reason.type != "requires_action":
                    break
        return "".join(text_parts)


class Archivist(ABC):
    """Records a player/World Soul exchange as structured data."""

    @abstractmethod
    def record(self, player_input: str, world_response: str) -> None:
        raise NotImplementedError


class IacsArchivist(Archivist):
    """Transcribes a player/World Soul exchange into iacs entity-first YAML.

    Runs a local tool-use loop rather than the hosted Anthropic Agents/
    Sessions platform `AgentWorld` uses, because that hosted API only accepts
    MCP servers reachable by URL and can't attach the local stdio `iacs-mcp`
    subprocess. The model is given the iacs MCP server's tools (describe_format,
    validate_yaml, ...) plus two local, non-MCP tools for reading/writing the
    world's save file, since no MCP tool writes new EC files.
    """

    def __init__(self, save_dir: Path, config_path: Path = PROD_ARCHIVIST_CONFIG_PATH):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        config = yaml.safe_load(config_path.read_text())
        if not config.get("system"):
            config["system"] = yaml.safe_load(PROD_ARCHIVIST_CONFIG_PATH.read_text())["system"]
        self.model = config["model"]
        self.system = config["system"]

    def record(self, player_input: str, world_response: str) -> None:
        asyncio.run(self._record_async(player_input, world_response))

    async def _record_async(self, player_input: str, world_response: str) -> None:
        async with open_iacs_mcp_session(self.save_dir) as mcp:
            tools = mcp.tools + [_WRITE_WORLD_FILE_TOOL, _READ_WORLD_FILE_TOOL]
            messages = [{"role": "user", "content": self._build_prompt(player_input, world_response)}]
            for _ in range(MAX_ARCHIVIST_TOOL_TURNS):
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self.system,
                    tools=tools,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})
                if response.stop_reason != "tool_use":
                    return
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    result_text = await self._dispatch_tool(mcp, block.name, block.input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                    )
                messages.append({"role": "user", "content": tool_results})

    @staticmethod
    def _build_prompt(player_input: str, world_response: str) -> str:
        return (
            f"Player input: {player_input}\n"
            f"World response: {world_response}\n\n"
            "Transcribe any entities/components this exchange reveals or changes "
            "into the world's save file."
        )

    async def _dispatch_tool(self, mcp, name: str, arguments: dict) -> str:
        if name == "write_world_file":
            return self._write_world_file(arguments["content"])
        if name == "read_world_file":
            return self._read_world_file()
        return await mcp.call_tool(name, arguments)

    def _write_world_file(self, content: str) -> str:
        path = self.save_dir / WORLD_YAML_FILENAME
        path.write_text(content)
        return f"Wrote {len(content)} characters to {path}."

    def _read_world_file(self) -> str:
        path = self.save_dir / WORLD_YAML_FILENAME
        if not path.exists():
            return "(world.yaml does not exist yet)"
        return path.read_text()


_WRITE_WORLD_FILE_TOOL = {
    "name": "write_world_file",
    "description": (
        "Overwrite the world's save file (world.yaml) with new entity-first "
        "YAML content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Full entity-first YAML content for world.yaml.",
            },
        },
        "required": ["content"],
    },
}

_READ_WORLD_FILE_TOOL = {
    "name": "read_world_file",
    "description": (
        "Read the world's current save file (world.yaml), if any, so it can "
        "be edited without clobbering entities recorded in prior turns."
    ),
    "input_schema": {"type": "object", "properties": {}},
}


class EnsembleWorld(World):
    """A world simulated by multiple interacting agents and systems.

    Each turn, the player's input is passed to the World Soul agent, which
    narrates how the world responds; each system (e.g. the Archivist) then
    gets a chance to record or react to the exchange. An iacs `Architect`,
    created at startup, acts as the data backend for querying the world's
    entities/components as they're recorded.
    """

    def __init__(
        self,
        world_soul: World | None = None,
        archivist: Archivist | None = None,
        save_dir: str | Path | None = None,
    ):
        self.world_soul = world_soul or AgentWorld()
        self.save_dir = Path(save_dir) if save_dir is not None else None
        if archivist is None and self.save_dir is not None:
            archivist = IacsArchivist(self.save_dir)
        self.archivist = archivist
        self.systems: list[Archivist] = [archivist] if archivist is not None else []
        self.architect = (
            Architect.from_manifest(self.save_dir) if self.save_dir is not None else Architect()
        )

    def respond(self, text: str) -> str:
        response = self.world_soul.respond(text)
        for system in self.systems:
            system.record(text, response)
        if self.save_dir is not None:
            self.architect.load_manifest(self.save_dir)
        return response
