from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path

import anthropic
import yaml
from iacs.architect import Architect

from story_simulator.config import ENVIRONMENT_ID, PROD_AGENT_ID, resolve_anthropic_api_key
from story_simulator.systems import (
    ArchivistAgentSystem,
    DEFAULT_RENDER_PATH,
    InputSystem,
    MapSystem,
    ResolverAgentSystem,
    VisualizerSystem,
)

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


class EnsembleWorld(World):
    """A world simulated by an ordered pipeline of Systems.

    Each turn, `respond()` runs every System in `systems` order against the
    same iacs `Architect`: by default, `MapSystem` first tags entities near
    the player as active (based on where the player ended up last turn),
    `InputSystem` registers the player's new input, `ResolverAgentSystem`
    narrates what happens, `ArchivistAgentSystem` transcribes the exchange
    into `world.yaml`, and `VisualizerSystem` re-renders the position plot.

    Defined here, alongside the other Worlds, rather than in
    story_simulator.systems — the System classes have no dependency on this
    module (each `AgentSystem` manages its own Anthropic client rather than
    delegating to a `World`), so there's no circular import to dodge.
    """

    def __init__(
        self,
        systems: "OrderedDict[str, object] | None" = None,
        save_dir: str | Path | None = None,
        render_path: str | Path | None = None,
    ):
        self.save_dir = Path(save_dir) if save_dir is not None else None
        self.architect = (
            Architect.from_manifest(self.save_dir) if self.save_dir is not None else Architect()
        )
        self.turn = 0
        self.systems = systems if systems is not None else self._default_systems(render_path)

    @staticmethod
    def _default_systems(render_path: str | Path | None) -> "OrderedDict[str, object]":
        return OrderedDict(
            map=MapSystem(),
            input=InputSystem(),
            resolver=ResolverAgentSystem(),
            archivist=ArchivistAgentSystem(),
            visualizer=VisualizerSystem(Path(render_path) if render_path else DEFAULT_RENDER_PATH),
        )

    def respond(self, text: str) -> str:
        self.turn += 1
        input_system = next(
            (s for s in self.systems.values() if isinstance(s, InputSystem)), None
        )
        if input_system is not None:
            input_system.receive(text)

        for system in self.systems.values():
            system.step(self.architect, self.save_dir, self.turn)

        resolver = next(
            (s for s in self.systems.values() if isinstance(s, ResolverAgentSystem)), None
        )
        return resolver.last_response if resolver else ""
