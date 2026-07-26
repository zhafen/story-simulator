import shutil
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path

import anthropic
import yaml
from iacs.registrar import Registrar
from iacs.registry import Registry

from story_simulator.config import (
    DEFAULT_WORLD_DIR,
    ENVIRONMENT_ID,
    PROD_AGENT_ID,
    resolve_anthropic_api_key,
)
from story_simulator.systems import (
    AgentSystem,
    ArchivistAgentSystem,
    DEFAULT_RENDER_PATH,
    ETLLoaderSystem,
    InputSystem,
    MapSystem,
    NPCAgentSystem,
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

    Each turn, `advance()` (or `respond()`, its human-player convenience
    wrapper) runs every System in `systems` order against the same iacs
    `Registrar` — the sole channel Systems use to communicate, per
    `Registrar`'s own role as the user-facing interface for viewing,
    updating, and exporting a registry. `world.yaml`, when present, is only
    ever a derived, human/AI-readable export of that registrar's registry;
    it's never read back in as authoritative (see
    `story_simulator.systems._export_world_yaml`). By default:
    `ETLLoaderSystem` first loads any not-yet-loaded EC files from
    `save_dir`, `MapSystem` tags entities near the turn's reference character
    as active (based on where that character ended up last turn — this first
    pass is what `ResolverAgentSystem` sees as "nearby" while narrating the
    action), `InputSystem` registers the human player's new input if any,
    `NPCAgentSystem` generates an NPC's input instead when no player command
    was given (see its docstring), `ResolverAgentSystem` narrates what
    happens, `ArchivistAgentSystem` transcribes the exchange (including any
    new position), `MapSystem` runs a second time so `active`/`memory`
    reflect where the move just landed rather than staying one turn stale
    for external readers, and `VisualizerSystem` re-renders the position
    plot.

    The registry itself — the actual save data — lives in
    `save_dir/registry.duckdb`: when `save_dir` is given, `Registrar.load`
    opens that file directly (creating it if it doesn't exist yet) rather
    than an in-memory connection, so every update lands straight in the
    file. DuckDB persists writes on a live connection automatically
    (confirmed: a second, independent connection to the same file sees a
    change immediately, with no explicit save step in between), so there's
    no separate `Registrar.save` call after each turn — that would just be
    reopening a second connection to a file the first connection is already
    keeping current.

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
        settings_fp: str | Path | None = None,
    ):
        self.save_dir = Path(save_dir) if save_dir is not None else None
        self.settings_fp = Path(settings_fp) if settings_fp is not None else None
        self.registrar = self._load_registrar()
        self.turn = 0
        self.systems = systems if systems is not None else self._default_systems(render_path)
        # Run the pipeline once at turn 0, with no player input pending, so the
        # starting state (loaded EC data, active tags from the reference
        # character's initial position) is queryable right after construction
        # rather than only after the first respond()/advance() call. Every
        # AgentSystem (NPCAgentSystem/ResolverAgentSystem/ArchivistAgentSystem)
        # is skipped outright here rather than left to self-bail on "no
        # command yet": that self-bail is what already kept
        # Resolver/Archivist inert at turn 0 (nothing has called InputSystem's
        # receive() yet), but NPCAgentSystem has no such external gate — left
        # unskipped, it would happily generate and resolve an NPC's first
        # command right here in the constructor, turning what's meant to be a
        # side-effect-free warmup pass into an unrequested real turn.
        for system in self.systems.values():
            if isinstance(system, AgentSystem):
                continue
            system.step(self.registrar, self.save_dir, self.turn)

    @property
    def registry(self) -> Registry:
        """The registrar's underlying registry, for callers that need direct read access."""
        return self.registrar.registry

    def _load_registrar(self) -> Registrar:
        if self.save_dir is not None:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            _seed_save_dir(self.save_dir, self.settings_fp)
            return Registrar.load(self.save_dir / REGISTRY_DB_FILENAME)
        return Registrar()

    @staticmethod
    def _default_systems(render_path: str | Path | None) -> "OrderedDict[str, object]":
        map_system = MapSystem()
        return OrderedDict(
            etl_loader=ETLLoaderSystem(),
            map=map_system,
            input=InputSystem(),
            npc_agent=NPCAgentSystem(),
            resolver=ResolverAgentSystem(),
            archivist=ArchivistAgentSystem(),
            # Re-tag active entities against the position the Archivist just
            # recorded (see class docstring) — same MapSystem instance, run
            # again rather than a second one, since it's stateless besides
            # `radius`.
            map_refresh=map_system,
            visualizer=VisualizerSystem(Path(render_path) if render_path else DEFAULT_RENDER_PATH),
        )

    def advance(self) -> str:
        """Run one turn of the systems pipeline, whether or not new player text is queued.

        `respond()` is a convenience wrapper over this for the human-player
        case; this is the primitive itself, for worlds where nothing but an
        NPCAgentSystem-driven NPC acts (see
        tests/test_human_validated.py::test_npc) and there's no player text
        to queue at all.
        """
        self.turn += 1
        for system in self.systems.values():
            system.step(self.registrar, self.save_dir, self.turn)

        resolver = next(
            (s for s in self.systems.values() if isinstance(s, ResolverAgentSystem)), None
        )
        return resolver.last_response if resolver else ""

    def respond(self, text: str) -> str:
        """
        Components
        ----------
        - todo: Can we avoid passing the text in? Maybe instead using a system that
            directly calls Python's input module, in the case of cli. If we set up an
            app later then a different system that's hooked up to FastAPI.
        """
        input_system = next(
            (s for s in self.systems.values() if isinstance(s, InputSystem)), None
        )
        if input_system is not None:
            input_system.receive(text)
        return self.advance()


def _seed_save_dir(save_dir: Path, settings_fp: Path | None) -> None:
    """Copy a starting scenario's save data into a brand-new, still-empty save_dir.

    `ETLLoaderSystem` only loads EC files already sitting in `save_dir`, so a
    fresh save directory never picks up any starting state on its own,
    leaving the Resolver to narrate a setting it has to invent from nothing.
    Copies from `settings_fp` when given — a hand-authored scenario the
    caller wants instead (e.g. tests/data/settings/npc, or the CLI's
    `--living` flag pointing this at `LIVING_WORLD_DIR`) — otherwise from
    `DEFAULT_WORLD_DIR`, so an ordinary sandbox always starts from the same
    plain premise rather than wherever the tracked living world currently
    stands. Skipped once `save_dir` already has any file in it — a prior
    save — and when `save_dir` already *is* the source dir itself (e.g.
    `EnsembleWorld(save_dir=DEFAULT_WORLD_DIR)`, where the source data
    already lives there — a no-op self-copy).
    """
    source_dir = settings_fp if settings_fp is not None else DEFAULT_WORLD_DIR
    if save_dir.resolve() == source_dir.resolve():
        return
    if any(save_dir.iterdir()):
        return
    shutil.copytree(source_dir, save_dir, dirs_exist_ok=True)
