import shutil
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path

import anthropic
import ibis
import yaml
from iacs.etl_system import ETLSystem
from iacs.registry import Registry

from story_simulator.config import ENVIRONMENT_ID, LIVING_WORLD_DIR, PROD_AGENT_ID, resolve_anthropic_api_key
from story_simulator.systems import (
    ArchivistAgentSystem,
    DEFAULT_RENDER_PATH,
    ETLLoaderSystem,
    InputSystem,
    MapSystem,
    REGISTRY_DB_FILENAME,
    ResolverAgentSystem,
    VisualizerSystem,
)

PROD_RESOLVER_CONFIG_PATH = Path(__file__).parent / "resolver.yaml"
TEST_RESOLVER_CONFIG_PATH = Path(__file__).parent / "resolver.test.yaml"


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
        config_path: Path = PROD_RESOLVER_CONFIG_PATH,
    ):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        self.agent_id = agent_id
        self.environment_id = environment_id
        self.config_path = config_path
        self.session_id = None

    def _load_config(self) -> dict:
        local = yaml.safe_load(self.config_path.read_text())
        if not local.get("system"):
            local["system"] = yaml.safe_load(PROD_RESOLVER_CONFIG_PATH.read_text())["system"]
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
    same iacs `Registry` — the sole channel Systems use to communicate.
    `world.yaml`, when present, is only ever a derived, human/AI-readable
    export of that registry; it's never read back in as authoritative (see
    `story_simulator.systems._export_world_yaml`). By default:
    `ETLLoaderSystem` first loads any not-yet-loaded EC files from
    `save_dir`, `MapSystem` tags entities near the player as active (based
    on where the player ended up last turn — this first pass is what
    `ResolverAgentSystem` sees as "nearby" while narrating the action),
    `InputSystem` registers the player's new input, `ResolverAgentSystem`
    narrates what happens, `ArchivistAgentSystem` transcribes the exchange
    (including any new player position), `MapSystem` runs a second time so
    `active` reflects where the move just landed rather than staying one
    turn stale for external readers, and `VisualizerSystem` re-renders the
    position plot.

    The registry itself — the actual save data — lives in
    `save_dir/registry.duckdb`: when `save_dir` is given, `Registry.from_database`
    opens that file directly (creating it if it doesn't exist yet) rather
    than an in-memory connection, so every `registry.merge`/`registry.update`
    write lands straight in the file. DuckDB persists writes on a live
    connection automatically (confirmed: a second, independent connection to
    the same file sees a change immediately, with no explicit save step in
    between), so there's no separate `to_database` call after each turn —
    that would just be reopening a second connection to a file the first
    connection is already keeping current.

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
        self.etl = ETLSystem()
        self.registry = self._load_registry()
        self.turn = 0
        self.systems = systems if systems is not None else self._default_systems(render_path)
        # Run the pipeline once at turn 0, with no player input pending, so the
        # starting state (loaded EC data, active tags from the player's initial
        # position) is queryable right after construction rather than only
        # after the first respond() call. ResolverAgentSystem/ArchivistAgentSystem
        # are no-ops here (they bail out when there's no player input recorded
        # for the turn), so this doesn't call out to any agent.
        for system in self.systems.values():
            system.step(self.registry, self.etl, self.save_dir, self.turn)

    def _load_registry(self) -> Registry:
        if self.save_dir is not None:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            _seed_from_living_world(self.save_dir)
            return Registry.from_database(self.save_dir / REGISTRY_DB_FILENAME)
        return Registry(ibis.duckdb.connect(), {})

    @staticmethod
    def _default_systems(render_path: str | Path | None) -> "OrderedDict[str, object]":
        map_system = MapSystem()
        return OrderedDict(
            etl_loader=ETLLoaderSystem(),
            map=map_system,
            input=InputSystem(),
            resolver=ResolverAgentSystem(),
            archivist=ArchivistAgentSystem(),
            # Re-tag active entities against the position the Archivist just
            # recorded (see class docstring) — same MapSystem instance, run
            # again rather than a second one, since it's stateless besides
            # `radius`.
            map_refresh=map_system,
            visualizer=VisualizerSystem(Path(render_path) if render_path else DEFAULT_RENDER_PATH),
        )

    def respond(self, text: str) -> str:
        """
        Components
        ----------
        - todo: Can we avoid passing the text in? Maybe instead using a system that
            directly calls Python's input module, in the case of cli. If we set up an
            app later then a different system that's hooked up to FastAPI.
        - todo: That might also fix the weirdness going on below with looping through
            the systems to find the resolver.
        - todo: After this change, we'll want to probably call this function "update".
        """
        self.turn += 1
        input_system = next(
            (s for s in self.systems.values() if isinstance(s, InputSystem)), None
        )
        if input_system is not None:
            input_system.receive(text)

        for system in self.systems.values():
            system.step(self.registry, self.etl, self.save_dir, self.turn)

        resolver = next(
            (s for s in self.systems.values() if isinstance(s, ResolverAgentSystem)), None
        )
        return resolver.last_response if resolver else ""


def _seed_from_living_world(save_dir: Path) -> None:
    """Copy the living world's current save data into a brand-new, still-empty save_dir.

    `ETLLoaderSystem` only loads EC files already sitting in `save_dir`, so a
    fresh sandbox save directory (the CLI's default) never picks up the
    living world's state on its own, leaving the Resolver to narrate a
    setting it has to invent from nothing. Copies everything under
    `LIVING_WORLD_DIR` rather than just the starting premise, so a new
    sandbox picks up wherever the living world currently stands, not just
    where it started. Skipped once `save_dir` already has any file in it —
    a prior save, or a hand-authored scenario the caller deliberately
    supplied instead — and when `save_dir` already *is* `LIVING_WORLD_DIR`
    (the `--living` flag), where the source data already lives (a no-op
    self-copy).
    """
    if save_dir.resolve() == LIVING_WORLD_DIR.resolve():
        return
    if any(save_dir.iterdir()):
        return
    shutil.copytree(LIVING_WORLD_DIR, save_dir, dirs_exist_ok=True)
