"""ECS-style Systems that drive an EnsembleWorld's turn loop.

Every turn, `EnsembleWorld` calls `step()` on each `System` in a fixed order.
Systems never call each other directly or pass return values between one
another; instead they communicate exclusively through the iacs `Architect`,
reading and writing `world.yaml` (and reloading the registry via
`architect.load_manifest(save_dir)`) so every value lives on the entity that
produced it: the player entity owns `input` components (its own commands and
the Resolver's narrated replies, distinguished by `type`), and each nearby
character/object owns a bare `active` tag for the turn.
"""

import asyncio
import math
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import matplotlib
import yaml
from iacs.architect import Architect

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from story_simulator.config import ENVIRONMENT_ID, PROD_AGENT_ID, resolve_anthropic_api_key
from story_simulator.mcp_client import open_iacs_mcp_session

WORLD_YAML_FILENAME = "world.yaml"
MAX_ARCHIVIST_TOOL_TURNS = 8
DEFAULT_ACTIVE_ENTITY_RADIUS = 20.0
DEFAULT_RENDER_PATH = Path("render.svg")

PROD_AGENT_CONFIG_PATH = Path(__file__).parent / "agent.yaml"
PROD_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.yaml"
TEST_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.test.yaml"


class System(ABC):
    """One stage of an EnsembleWorld turn."""

    @abstractmethod
    def step(self, architect: Architect, save_dir: Path | None, turn: int) -> None:
        raise NotImplementedError


class InputSystem(System):
    """Registers the player's raw input as an `input` component on the player entity."""

    def __init__(self):
        self._pending_text: str | None = None

    def receive(self, text: str) -> None:
        """Queue the player's raw text for the next step() call."""
        self._pending_text = text

    def step(self, architect: Architect, save_dir: Path | None, turn: int) -> None:
        if save_dir is None or self._pending_text is None:
            return
        alias = _ensure_player_alias(save_dir, architect)
        _add_input(save_dir, alias, self._pending_text, "player", turn)
        self._pending_text = None


class AgentSystem(System, ABC):
    """Base class for Systems whose step() calls out to an Anthropic agent."""


class MapSystem(System):
    """Tags characters/objects within `radius` of the player as `active` for the turn.

    Reads the player's position as of the *previous* turn's recorded data
    (this System runs before `InputSystem`/`ResolverAgentSystem` each turn),
    and adds/removes a bare `active` tag directly on each entity as it enters
    or leaves range.
    """

    def __init__(self, radius: float = DEFAULT_ACTIVE_ENTITY_RADIUS):
        self.radius = radius

    def step(self, architect: Architect, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        player = _player_position(architect)
        if player is None:
            return
        player_alias, player_pos = player

        active_aliases = set()
        for component, label_field in (("character", "interaction_type"), ("object", "type")):
            if component not in architect.registry.component_types:
                continue
            view = architect.view([f"{component}.{label_field}", "position.x", "position.y"])
            try:
                df = view.execute()
            except KeyError:
                continue
            for _, row in df.iterrows():
                alias = row["entity_id.alias"]
                if alias == player_alias:
                    continue
                pos = (float(row["position.x"]), float(row["position.y"]))
                if math.dist(pos, player_pos) <= self.radius:
                    active_aliases.add(alias)

        _sync_active_tags(save_dir, active_aliases)


class ResolverAgentSystem(AgentSystem):
    """Resolves what the player sees and what happens, via the Resolver agent.

    Reads the turn's player input and active entities from the registry,
    prompts the hosted Anthropic Agents/Sessions platform directly (its own
    client and session, independent of the `World` hierarchy), and writes
    the result back as an agent-type `input` component on the player entity.
    This duplicates `AgentWorld`'s session-management logic rather than
    delegating to it, so this System has no dependency on story_simulator.world.
    """

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
        self.last_response: str = ""

    def step(self, architect: Architect, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        command_text = _latest_input(save_dir, "player", turn)
        if command_text is None:
            return

        active_aliases = _active_aliases(save_dir)
        response = self._respond(_build_prompt(command_text, active_aliases))
        self.last_response = response

        alias = _ensure_player_alias(save_dir, architect)
        _add_input(save_dir, alias, response, "agent", turn)

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

    def _respond(self, text: str) -> str:
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


class ArchivistAgentSystem(AgentSystem):
    """Transcribes a turn's input exchange into iacs entity-first YAML.

    Runs a local tool-use loop rather than the hosted Anthropic Agents/
    Sessions platform `AgentWorld` uses, because that hosted API only accepts
    MCP servers reachable by URL and can't attach the local stdio `iacs-mcp`
    subprocess. The tool loop is async because the `mcp` SDK's stdio
    transport (`open_iacs_mcp_session`) is itself async-only. The model is
    given the iacs MCP server's tools (describe_format, validate_yaml, ...)
    plus two local, non-MCP tools for reading/writing the world's save file,
    since no MCP tool writes new EC files.
    """

    def __init__(self, config_path: Path = PROD_ARCHIVIST_CONFIG_PATH):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        config = yaml.safe_load(config_path.read_text())
        if not config.get("system"):
            config["system"] = yaml.safe_load(PROD_ARCHIVIST_CONFIG_PATH.read_text())["system"]
        self.model = config["model"]
        self.system = config["system"]

    def step(self, architect: Architect, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        command_text = _latest_input(save_dir, "player", turn)
        narration_text = _latest_input(save_dir, "agent", turn)
        if command_text is None or narration_text is None:
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

    def step(self, architect: Architect, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        has_positions = "position" in architect.registry.component_types
        if has_positions:
            position = architect.view("position")
            df = position.execute()

        fig, ax = plt.subplots()
        if has_positions and not df.empty:
            ax.scatter(df["position.x"], df["position.y"])
            for _, row in df.iterrows():
                ax.annotate(
                    row["entity_id.alias"],
                    (row["position.x"], row["position.y"]),
                    xytext=(5, 5),
                    textcoords="offset points",
                )
        ax.set_aspect("equal", adjustable="datalim")
        fig.savefig(self.render_path)
        plt.close(fig)


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


def _read_world_yaml(save_dir: Path) -> dict:
    path = Path(save_dir) / WORLD_YAML_FILENAME
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _write_world_yaml(save_dir: Path, data: dict) -> None:
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / WORLD_YAML_FILENAME).write_text(yaml.safe_dump(data, sort_keys=False))


def _add_input(save_dir: Path, alias: str, text: str, type_: str, turn: int) -> None:
    """Append an `input` component instance onto `alias`'s entity."""
    data = _read_world_yaml(save_dir)
    components = data.setdefault(alias, [])
    components.append({"input": {"text": text, "type": type_, "turn": turn}})
    _write_world_yaml(save_dir, data)


def _sync_active_tags(save_dir: Path, active_aliases: set[str]) -> None:
    """Add/remove the bare `active` tag on each entity to match `active_aliases`."""
    data = _read_world_yaml(save_dir)
    for alias, components in data.items():
        has_tag = "active" in components
        should_have_tag = alias in active_aliases
        if should_have_tag and not has_tag:
            components.append("active")
        elif not should_have_tag and has_tag:
            components.remove("active")
    _write_world_yaml(save_dir, data)


def _player_alias(architect: Architect) -> str | None:
    """Return the current player entity's alias, or None if it doesn't exist yet."""
    if "character" not in architect.registry.component_types:
        return None
    view = architect.view(["character.interaction_type"])
    df = view.filter(view["character.interaction_type"] == "player").execute()
    if df.empty:
        return None
    return df.iloc[0]["entity_id.alias"]


def _player_position(architect: Architect) -> tuple[str, tuple[float, float]] | None:
    """Return (alias, (x, y)) for the player entity, or None if not known yet."""
    if "character" not in architect.registry.component_types:
        return None
    if "position" not in architect.registry.component_types:
        return None
    view = architect.view(["character.interaction_type", "position.x", "position.y"])
    try:
        df = view.filter(view["character.interaction_type"] == "player").execute()
    except KeyError:
        return None
    if df.empty:
        return None
    row = df.iloc[0]
    return row["entity_id.alias"], (float(row["position.x"]), float(row["position.y"]))


def _ensure_player_alias(save_dir: Path, architect: Architect) -> str:
    """Return the player entity's alias, seeding a minimal one if none exists yet.

    On the very first turn there's no player entity for InputSystem/
    ResolverAgentSystem to attach an `input` component to, since the
    Archivist only creates one once it transcribes the first exchange. Seed
    a bare `player` entity (matching the alias archivist.yaml already
    instructs the Archivist to use) so `input` always has somewhere to live.
    """
    alias = _player_alias(architect)
    if alias is not None:
        return alias
    data = _read_world_yaml(save_dir)
    if "player" not in data:
        data["player"] = [{"character": {"interaction_type": "player"}}]
        _write_world_yaml(save_dir, data)
        architect.load_manifest(save_dir)
    return "player"


def _latest_input(save_dir: Path, type_: str, turn: int) -> str | None:
    """Return the `type_`-authored input's text for `turn`, or None if not written yet.

    Reads through a fresh, throwaway Architect scoped to `save_dir` rather
    than the long-lived one EnsembleWorld keeps, so a same-turn write by an
    earlier System (e.g. InputSystem, moments before ResolverAgentSystem
    runs) is visible without reloading (and thereby accumulating history
    into) the long-lived registry.

    Without a validated schema loaded, iacs keeps field values as raw
    strings rather than casting `turn` to int, so the comparison is done on
    the string form of `turn` to stay dtype-agnostic.
    """
    registry = Architect.from_manifest(save_dir)
    if "input" not in registry.registry.component_types:
        return None
    i = registry.get("input")
    df = i.filter(i.type == type_).execute()
    matches = df[df["turn"].astype(str) == str(turn)]
    if matches.empty:
        return None
    return matches.iloc[-1]["text"]


def _active_aliases(save_dir: Path) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    registry = Architect.from_manifest(save_dir)
    if "active" not in registry.registry.component_types:
        return set()
    view = registry.view("active")
    df = view.execute()
    return set(df["entity_id.alias"])


def _build_prompt(text: str, active_aliases: set[str]) -> str:
    """Combine the player's input with the list of active entities."""
    if not active_aliases:
        return text
    entities = ", ".join(sorted(active_aliases))
    return f"Active entities nearby: {entities}\nPlayer input: {text}"
