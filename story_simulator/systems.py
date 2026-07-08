"""ECS-style Systems that drive an EnsembleWorld's turn loop.

Every turn, `EnsembleWorld` calls `step()` on each `System` in a fixed order.
Systems never call each other directly or pass return values between one
another; instead they communicate exclusively through the iacs `Architect`
(`architect`), reading and writing entity-first YAML files under `save_dir`
and reloading the registry via `architect.load_manifest(save_dir)`. Two
scratch component types, `command` and `narration`, plus a tag component,
`active`, carry each turn's ephemeral state (the player's raw input, the
World Soul's narration, and which entities are currently near the player) on
a dedicated `turn_log` entity, alongside the "real" entities (`player`,
`door`, ...) that `ArchivistAgentSystem` transcribes into `world.yaml`.
"""

import asyncio
import math
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path

import anthropic
import yaml
from iacs.architect import Architect

from story_simulator.config import resolve_anthropic_api_key
from story_simulator.mcp_client import open_iacs_mcp_session
from story_simulator.positions import get_labeled_positions
from story_simulator.render import DEFAULT_RENDER_PATH, render_positions
from story_simulator.world import AgentWorld, World

WORLD_YAML_FILENAME = "world.yaml"
TURN_LOG_FILENAME = "turn_log.yaml"
TURN_LOG_ALIAS = "turn_log"
MAX_ARCHIVIST_TOOL_TURNS = 8
DEFAULT_ACTIVE_ENTITY_RADIUS = 20.0

PROD_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.yaml"
TEST_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.test.yaml"


class System(ABC):
    """One stage of an EnsembleWorld turn.

    `text` is the player's raw input for the turn; every System receives it
    so the interface stays uniform, but only `InputSystem` actually uses it
    (everyone downstream reads the `command` component it writes instead).
    """

    @abstractmethod
    def step(self, architect: Architect, save_dir: Path | None, turn: int, text: str) -> None:
        raise NotImplementedError


class InputSystem(System):
    """Registers the player's raw input as a `command` component for the turn."""

    def step(self, architect: Architect, save_dir: Path | None, turn: int, text: str) -> None:
        if save_dir is None:
            return
        _write_turn_component(save_dir, "command", {"text": text, "turn": turn})


class AgentSystem(System, ABC):
    """Base class for Systems whose step() calls out to an Anthropic agent."""


class MapSystem(System):
    """Tags characters/objects within `radius` of the player as `active` for the turn.

    Reads the player's position as of the *previous* turn's recorded data
    (this System runs before `InputSystem`/`ResolverAgentSystem` each turn),
    and writes an `active` component instance per nearby entity onto the
    `turn_log` entity.
    """

    def __init__(self, radius: float = DEFAULT_ACTIVE_ENTITY_RADIUS):
        self.radius = radius

    def step(self, architect: Architect, save_dir: Path | None, turn: int, text: str) -> None:
        if save_dir is None:
            return
        player = self._find_player(architect)
        if player is None:
            return
        player_id, player_pos = player
        tags = []
        for kind, label_field in (("character", "interaction_type"), ("object", "type")):
            for entity_id, label, pos in get_labeled_positions(architect, kind, label_field):
                if entity_id == player_id:
                    continue
                if math.dist(pos, player_pos) <= self.radius:
                    tags.append({"target": entity_id, "kind": kind, "label": label, "turn": turn})
        _write_turn_components(save_dir, "active", tags)

    @staticmethod
    def _find_player(architect: Architect) -> tuple[str, tuple[float, float]] | None:
        for entity_id, label, pos in get_labeled_positions(
            architect, "character", "interaction_type"
        ):
            if label == "player":
                return entity_id, pos
        return None


class ResolverAgentSystem(AgentSystem):
    """Resolves what the player sees and what happens, via the World Soul agent.

    Reads the turn's `command` and `active` components from the registry,
    prompts `world_soul` (an `AgentWorld` by default), and writes the result
    back as the turn's `narration` component. Also keeps the response on
    `last_response` so `EnsembleWorld.respond()` has something to return even
    when there's no `save_dir` (and therefore no registry) to write through.
    """

    def __init__(self, world_soul: World | None = None):
        self.world_soul = world_soul or AgentWorld()
        self.last_response: str = ""

    def step(self, architect: Architect, save_dir: Path | None, turn: int, text: str) -> None:
        if save_dir is not None:
            command_text = _latest_turn_value(save_dir, "command", turn) or text
            active = _active_entities_for_turn(save_dir, turn)
        else:
            command_text = text
            active = []

        response = self.world_soul.respond(_build_prompt(command_text, active))
        self.last_response = response

        if save_dir is not None:
            _write_turn_component(save_dir, "narration", {"text": response, "turn": turn})


class ArchivistAgentSystem(AgentSystem):
    """Transcribes a turn's command/narration exchange into iacs entity-first YAML.

    Runs a local tool-use loop rather than the hosted Anthropic Agents/
    Sessions platform `AgentWorld` uses, because that hosted API only accepts
    MCP servers reachable by URL and can't attach the local stdio `iacs-mcp`
    subprocess. The model is given the iacs MCP server's tools (describe_format,
    validate_yaml, ...) plus two local, non-MCP tools for reading/writing the
    world's save file, since no MCP tool writes new EC files.
    """

    def __init__(self, config_path: Path = PROD_ARCHIVIST_CONFIG_PATH):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        config = yaml.safe_load(config_path.read_text())
        if not config.get("system"):
            config["system"] = yaml.safe_load(PROD_ARCHIVIST_CONFIG_PATH.read_text())["system"]
        self.model = config["model"]
        self.system = config["system"]

    def step(self, architect: Architect, save_dir: Path | None, turn: int, text: str) -> None:
        if save_dir is None:
            return
        command_text = _latest_turn_value(save_dir, "command", turn) or text
        narration_text = _latest_turn_value(save_dir, "narration", turn)
        if narration_text is None:
            return
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        asyncio.run(self._record_async(save_dir, command_text, narration_text))
        architect.load_manifest(save_dir)

    async def _record_async(self, save_dir: Path, player_input: str, world_response: str) -> None:
        async with open_iacs_mcp_session(save_dir) as mcp:
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
                    result_text = await self._dispatch_tool(mcp, save_dir, block.name, block.input)
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

    async def _dispatch_tool(self, mcp, save_dir: Path, name: str, arguments: dict) -> str:
        if name == "write_world_file":
            return self._write_world_file(save_dir, arguments["content"])
        if name == "read_world_file":
            return self._read_world_file(save_dir)
        return await mcp.call_tool(name, arguments)

    @staticmethod
    def _write_world_file(save_dir: Path, content: str) -> str:
        path = save_dir / WORLD_YAML_FILENAME
        path.write_text(content)
        return f"Wrote {len(content)} characters to {path}."

    @staticmethod
    def _read_world_file(save_dir: Path) -> str:
        path = save_dir / WORLD_YAML_FILENAME
        if not path.exists():
            return "(world.yaml does not exist yet)"
        return path.read_text()


class VisualizerSystem(System):
    """Renders an SVG scatter plot of every positioned entity, each turn."""

    def __init__(self, render_path: Path = DEFAULT_RENDER_PATH):
        self.render_path = Path(render_path)

    def step(self, architect: Architect, save_dir: Path | None, turn: int, text: str) -> None:
        if save_dir is None:
            return
        render_positions(architect, self.render_path)


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


def _read_turn_log(save_dir: Path) -> dict:
    path = Path(save_dir) / TURN_LOG_FILENAME
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _write_turn_components(save_dir: Path, component: str, entries: list[dict]) -> None:
    """Replace all `component` instances on the `turn_log` entity with `entries`."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    data = _read_turn_log(save_dir)
    kept = [
        item
        for item in data.get(TURN_LOG_ALIAS, [])
        if not (isinstance(item, dict) and component in item)
    ]
    data[TURN_LOG_ALIAS] = kept + [{component: fields} for fields in entries]
    (save_dir / TURN_LOG_FILENAME).write_text(yaml.safe_dump(data, sort_keys=False))


def _write_turn_component(save_dir: Path, component: str, fields: dict) -> None:
    _write_turn_components(save_dir, component, [fields])


def _load_turn_registry(save_dir: Path) -> Architect:
    """Load a throwaway Architect scoped to `save_dir`'s current file contents.

    `command`/`narration`/`active` are ephemeral, single-turn values, so
    reading them through a fresh Architect (rather than the long-lived one
    EnsembleWorld keeps for "real" entities) avoids accumulating every past
    turn's now-irrelevant rows into a permanently growing table.
    """
    return Architect.from_manifest(save_dir)


def _latest_turn_value(save_dir: Path, component: str, turn: int) -> str | None:
    """Return `component.text` for `turn`, or None if it hasn't been written yet.

    Without a validated schema loaded, iacs keeps field values as raw
    strings rather than casting `turn` to int, so the comparison is done on
    the string form of `turn` to stay dtype-agnostic.
    """
    registry = _load_turn_registry(save_dir)
    try:
        df = registry.view([f"{component}.text", f"{component}.turn"]).execute()
    except KeyError:
        return None
    matches = df[df[f"{component}.turn"].astype(str) == str(turn)]
    if matches.empty:
        return None
    return matches.iloc[-1][f"{component}.text"]


def _active_entities_for_turn(save_dir: Path, turn: int) -> list[dict]:
    """Return {id, kind, label} for every entity tagged `active` this turn."""
    registry = _load_turn_registry(save_dir)
    try:
        df = registry.view(
            ["active.target", "active.kind", "active.label", "active.turn"]
        ).execute()
    except KeyError:
        return []
    matches = df[df["active.turn"].astype(str) == str(turn)]
    return [
        {"id": row["active.target"], "kind": row["active.kind"], "label": row["active.label"]}
        for _, row in matches.iterrows()
    ]


def _build_prompt(text: str, active: list[dict]) -> str:
    """Combine the player's input with the list of active entities."""
    if not active:
        return text
    entities = ", ".join(f"{e['label']} ({e['kind']}: {e['id']})" for e in active)
    return f"Active entities nearby: {entities}\nPlayer input: {text}"


class EnsembleWorld(World):
    """A world simulated by an ordered pipeline of Systems.

    Each turn, `respond()` runs every System in `systems` order against the
    same iacs `Architect`: by default, `MapSystem` first tags entities near
    the player as active (based on where the player ended up last turn),
    `InputSystem` registers the player's new input, `ResolverAgentSystem`
    narrates what happens, `ArchivistAgentSystem` transcribes the exchange
    into `world.yaml`, and `VisualizerSystem` re-renders the position plot.
    """

    def __init__(
        self,
        systems: "OrderedDict[str, System] | None" = None,
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
    def _default_systems(render_path: str | Path | None) -> "OrderedDict[str, System]":
        return OrderedDict(
            map=MapSystem(),
            input=InputSystem(),
            resolver=ResolverAgentSystem(),
            archivist=ArchivistAgentSystem(),
            visualizer=VisualizerSystem(Path(render_path) if render_path else DEFAULT_RENDER_PATH),
        )

    def respond(self, text: str) -> str:
        self.turn += 1
        for system in self.systems.values():
            system.step(self.architect, self.save_dir, self.turn, text)
        resolver = next(
            (s for s in self.systems.values() if isinstance(s, ResolverAgentSystem)), None
        )
        return resolver.last_response if resolver else ""
