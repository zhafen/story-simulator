from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import yaml

from story_simulator.config import ENVIRONMENT_ID, PROD_AGENT_ID

PROD_AGENT_CONFIG_PATH = Path(__file__).parent / "agent.yaml"
TEST_AGENT_CONFIG_PATH = Path(__file__).parent / "agent.test.yaml"


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
        self.client = anthropic.Anthropic()
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
    """Records a player/World Soul exchange as structured data.

    Not yet implemented — a concrete Archivist agent is coming soon.
    """

    @abstractmethod
    def record(self, player_input: str, world_response: str) -> None:
        raise NotImplementedError


class EnsembleWorld(World):
    """A world simulated by multiple interacting agents and systems.

    Each turn, the player's input is passed to the World Soul agent, which
    narrates how the world responds; the Archivist agent then records the
    exchange as structured data. The Archivist is optional for now since it
    isn't implemented yet.
    """

    def __init__(self, world_soul: World | None = None, archivist: Archivist | None = None):
        self.world_soul = world_soul or AgentWorld()
        self.archivist = archivist

    def respond(self, text: str) -> str:
        response = self.world_soul.respond(text)
        if self.archivist is not None:
            self.archivist.record(text, response)
        return response
