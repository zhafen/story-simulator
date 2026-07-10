"""ECS-style Systems that drive an EnsembleWorld's turn loop.

Every turn, `EnsembleWorld` calls `step()` on each `System` in a fixed order.
Systems never call each other directly or pass return values between one
another; instead they communicate exclusively through the iacs `Registry`
(a shared, long-lived object every System reads and mutates directly), so
every value lives on the entity that produced it: the player entity owns
`input` components (its own commands and the Resolver's narrated replies,
distinguished by `type`), and each nearby character/object owns a bare
`active` tag for the turn. `ETLLoaderSystem` runs first each turn to pick up
any EC files in `save_dir` that nothing has fed into the registry yet.
`world.yaml` is only ever a derived, human/AI-readable export of the
registry (written by `ArchivistAgentSystem`) — nothing reads it back in as
authoritative; the actual save data is the registry itself, persisted via
`Registry.to_database`/`Registry.from_database`.
"""

import asyncio
import math
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import ibis
import matplotlib
import pandas as pd
import yaml
from iacs.dataflows import base_etl
from iacs.dataflows.etl import export_manifest
from iacs.etl_system import ETLSystem
from iacs.registry import Registry

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from story_simulator.config import ENVIRONMENT_ID, PROD_AGENT_ID, resolve_anthropic_api_key
from story_simulator.mcp_client import open_iacs_mcp_session

WORLD_YAML_FILENAME = "world.yaml"
REGISTRY_DB_FILENAME = "registry.duckdb"
WORLD_FILE_ID = "world"
MAX_ARCHIVIST_TOOL_TURNS = 8
DEFAULT_ACTIVE_ENTITY_RADIUS = 20.0
DEFAULT_RENDER_PATH = Path("render.svg")
EC_FILE_GLOBS = ("*.yaml", "*.yml", "*.py", "*.csv")

PROD_AGENT_CONFIG_PATH = Path(__file__).parent / "agent.yaml"
PROD_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.yaml"
TEST_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.test.yaml"
SETTING_CONFIG_PATH = Path(__file__).parent / "setting.yaml"


class System(ABC):
    """One stage of an EnsembleWorld turn."""

    @abstractmethod
    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        raise NotImplementedError


class ETLLoaderSystem(System):
    """Loads any not-yet-loaded EC files from `save_dir` into the registry.

    Runs first each turn so every other System sees the latest on-disk
    state. Tracks every file path already merged in `loaded_files`, so a
    file is loaded exactly once. `world.yaml` is always skipped: it's a
    derived export of the registry (see `_export_world_yaml`), not an
    independent source, and reloading it would mint duplicate entities under
    a different file identifier than the `WORLD_FILE_ID` every direct
    registry merge already uses. This System exists to pick up files
    nothing else has fed in yet, such as a save directory's pre-existing,
    hand-authored EC manifests on startup, or a new one dropped into
    `save_dir` mid-game.

    Components
    ----------
    - todo: I don't think we track loaded_files across sessions, so there's a risk of
        duplication if the same file exists. I think instead we should ensure iacs
        tracks the files loaded as part of the load_manifest etl and then just refer
        to that.
    """

    def __init__(self):
        self.loaded_files: set[Path] = set()

    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        save_dir = Path(save_dir)
        if not save_dir.exists():
            return
        found = {
            f
            for pattern in EC_FILE_GLOBS
            for f in save_dir.rglob(pattern)
            if f.name != WORLD_YAML_FILENAME
        }
        new_files = sorted(found - self.loaded_files)
        if not new_files:
            return
        new_registry = etl.execute(base_etl, input_dirs=[str(f) for f in new_files])
        registry.merge(new_registry)
        new_registry.close()
        self.loaded_files.update(new_files)


class InputSystem(System):
    """Registers the player's raw input as an `input` component on the player entity."""

    def __init__(self):
        self._pending_text: str | None = None

    def receive(self, text: str) -> None:
        """Queue the player's raw text for the next step() call."""
        self._pending_text = text

    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        if save_dir is None or self._pending_text is None:
            return
        alias = _ensure_player_alias(registry, etl)
        _add_input(registry, etl, alias, self._pending_text, "player", turn)
        self._pending_text = None


class AgentSystem(System, ABC):
    """Base class for Systems whose step() calls out to an Anthropic agent.

    Components
    ----------
    - todo: Why have this defined here, instead of adjacent to the agent systems?
    """


class MapSystem(System):
    """Tags characters/objects within `radius` of the player as `active` for the turn.

    Reads the player's position as of the *previous* turn's recorded data
    (this System runs before `InputSystem`/`ResolverAgentSystem` each turn),
    and adds/removes a bare `active` tag directly on each entity as it enters
    or leaves range.

    Components
    ----------
    - todo: Reincorporate z-axis.
    """

    def __init__(self, radius: float = DEFAULT_ACTIVE_ENTITY_RADIUS):
        self.radius = radius

    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        player = _player_position(registry)
        if player is None:
            return
        player_alias, player_pos = player
        # entity_id.alias is left out here: label_df (below) already carries its
        # own copy via registry.view(), and merging on entity_id would otherwise
        # produce two colliding entity_id.alias columns.
        positions = _latest_positions(registry)[["entity_id", "position.x", "position.y"]]

        active_aliases = set()
        for component, label_field in (("character", "interaction_type"), ("object", "type")):
            if component not in registry.component_types:
                continue
            try:
                label_df = registry.view([f"{component}.{label_field}"]).execute()
            except KeyError:
                continue
            for _, row in label_df.merge(positions, on="entity_id").iterrows():
                alias = row["entity_id.alias"]
                if alias == player_alias:
                    continue
                pos = (float(row["position.x"]), float(row["position.y"]))
                if math.dist(pos, player_pos) <= self.radius:
                    active_aliases.add(alias)

        _sync_active_tags(registry, etl, active_aliases)


class ResolverAgentSystem(AgentSystem):
    """Resolves what the player sees and what happens, via the Resolver agent.

    Reads the turn's player input and active entities from the registry,
    prompts the hosted Anthropic Agents/Sessions platform directly (its own
    client and session, independent of the `World` hierarchy), and writes
    the result back as an agent-type `input` component on the player entity.
    This duplicates `AgentWorld`'s session-management logic rather than
    delegating to it, so this System has no dependency on story_simulator.world.

    The world's setting (its starting premise) lives in `setting.yaml`
    rather than being baked into the agent's system prompt, so `_build_prompt`
    can fold it into every turn instead of relying on the model to remember
    it from the start of a session. The hosted Agents/Sessions platform this
    System narrates through only accepts MCP servers reachable by URL, so it
    can't attach the local stdio `iacs-mcp` subprocess directly (see
    `ArchivistAgentSystem`); instead, this System talks to `iacs-mcp` itself
    as a plain MCP client (`_gather_entity_details`) to look up what's known
    about each active entity, and folds that into the prompt text too.
    """

    def __init__(
        self,
        agent_id: str = PROD_AGENT_ID,
        environment_id: str = ENVIRONMENT_ID,
        config_path: Path = PROD_AGENT_CONFIG_PATH,
        setting_path: Path = SETTING_CONFIG_PATH,
    ):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        self.agent_id = agent_id
        self.environment_id = environment_id
        self.config_path = config_path
        self.setting_path = setting_path
        self.session_id = None
        self.last_response: str = ""

    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        """
        Components
        ----------
        - todo: What does _ensure_player_alias do?
        """
        if save_dir is None:
            return
        command_text = _latest_input(registry, "player", turn)
        if command_text is None:
            return

        active_aliases = _active_aliases(registry)
        entity_details = asyncio.run(self._gather_entity_details(Path(save_dir), active_aliases))
        prompt = _build_prompt(
            command_text,
            active_aliases,
            setting=_load_setting(self.setting_path),
            entity_details=entity_details,
        )
        response = self._respond(prompt)
        self.last_response = response

        alias = _ensure_player_alias(registry, etl)
        _add_input(registry, etl, alias, response, "agent", turn)

    async def _gather_entity_details(self, save_dir: Path, active_aliases: set[str]) -> str:
        """Ask the local iacs MCP server what's known about each active entity.

        Only opens a session when there's something to look up, so turns
        with no active entities (including every "does nothing" early-return
        case) never pay for spawning the `iacs-mcp` subprocess.
        """
        if not active_aliases:
            return ""
        async with open_iacs_mcp_session(save_dir) as mcp:
            views = [
                await mcp.call_tool("view_entity", {"entity_id": alias})
                for alias in sorted(active_aliases)
            ]
        return "\n".join(views)

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
    since no MCP tool writes new EC files. The content of the last
    `write_world_file` call is fed straight to `ETLSystem` as a YAML string
    and merged into the registry, rather than reloading `save_dir` from
    disk. `world.yaml` itself is regenerated from the registry (via iacs's
    `export_manifest`) before and after the tool loop, so `read_world_file`
    sees the full current save data and the on-disk export stays in sync
    with whatever this step merged in.

    Components
    ----------
    - todo: The docstrings are too verbose, explaining a lot of old context-specific
        reasoning. That's true for this entity and others.
    - todo: Not sure we need to export world.yaml every turn.
    - todo: The tools should be handled fully as part of iacs. We shouldn't need custom
        tools for iacs I/O.
    """

    def __init__(self, config_path: Path = PROD_ARCHIVIST_CONFIG_PATH):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        config = yaml.safe_load(config_path.read_text())
        if not config.get("system"):
            config["system"] = yaml.safe_load(PROD_ARCHIVIST_CONFIG_PATH.read_text())["system"]
        self.model = config["model"]
        self.system = config["system"]
        self._last_content: str | None = None

    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        command_text = _latest_input(registry, "player", turn)
        narration_text = _latest_input(registry, "agent", turn)
        if command_text is None or narration_text is None:
            return
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        _export_world_yaml(registry, etl, save_dir)
        self._last_content = None
        asyncio.run(self._record_async(save_dir, command_text, narration_text))
        if self._last_content is not None:
            _merge_yaml_string(registry, etl, WORLD_FILE_ID, self._last_content, turn)
            _export_world_yaml(registry, etl, save_dir)

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
            self._last_content = arguments["content"]
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

    def step(self, registry: Registry, etl: ETLSystem, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        has_positions = "position" in registry.component_types
        if has_positions:
            df = _latest_positions(registry)

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


def _merge_yaml_string(
    registry: Registry, etl: ETLSystem, key: str, yaml_text: str, turn: int | None = None
) -> None:
    """Run the ETL pipeline on a raw YAML string and merge the result into `registry`.

    If `turn` is given, stamps it onto every `position` row before merging.
    Unlike `input` (whose `turn` is set explicitly by `_add_input`), `position`
    is written from the Archivist's freeform YAML, which has no reason to know
    about the turn counter — so it's filled in here instead. `position` rows
    accumulate across turns rather than being overwritten (`registry.merge`
    only unions rows in), so this `turn` column is what lets readers resolve
    which row is current; see `_latest_positions`.
    """
    new_registry = etl.execute(base_etl, input_dirs=[], yaml_strings={key: yaml_text})
    if turn is not None and "position" in new_registry.component_types:
        stamped = new_registry.get("position").mutate(turn=ibis.literal(turn))
        new_registry.update({"position": stamped})
    registry.merge(new_registry)
    new_registry.close()


def _export_world_yaml(registry: Registry, etl: ETLSystem, save_dir: Path) -> None:
    """Regenerate `world.yaml` as a human/AI-readable export of the registry's state.

    Purely a derived artifact — the registry (persisted via
    `Registry.to_database`/`Registry.from_database`) is the actual save
    data, and nothing reads this file back in. Written via iacs's own
    `export_manifest` dataflow, which writes one output file per original
    source identifier; every direct registry merge in this module uses
    `WORLD_FILE_ID` ("world"), which `export_manifest` suffixes into
    `world.yaml`.
    """
    etl.execute(export_manifest, registry=registry, output_dir=str(save_dir))


def _input_history(registry: Registry, alias: str) -> list[dict]:
    """Return every existing `input` component instance on `alias`'s entity."""
    if "input" not in registry.component_types:
        return []
    view = registry.view(["input.text", "input.type", "input.turn"])
    df = view.filter(view["entity_id.alias"] == alias).execute()
    return [
        {"text": row["input.text"], "type": row["input.type"], "turn": row["input.turn"]}
        for _, row in df.iterrows()
    ]


def _add_input(registry: Registry, etl: ETLSystem, alias: str, text: str, type_: str, turn: int) -> None:
    """Merge a new `input` component instance onto `alias`'s entity.

    Rebuilds and overwrites the whole `input` component table from
    `alias`'s full history plus the new instance, rather than unioning in
    just the new row — `registry.merge` would otherwise collide every call
    on the same `component_index` (each call's YAML fragment is its own
    single-item list, always indexed 0). Safe to overwrite wholesale: only
    `InputSystem`/`ResolverAgentSystem` ever write `input`, and always onto
    the one player entity.
    """
    history = _input_history(registry, alias) + [{"text": text, "type": type_, "turn": turn}]
    data = {alias: [{"input": h} for h in history]}
    new_registry = etl.execute(base_etl, input_dirs=[], yaml_strings={WORLD_FILE_ID: yaml.safe_dump(data, sort_keys=False)})
    # .to_pyarrow() materializes the data so it can cross from new_registry's
    # connection into registry's (mirrors Registry.merge's own approach).
    registry.update({"input": new_registry.get("input").to_pyarrow()})
    new_registry.close()


def _sync_active_tags(registry: Registry, etl: ETLSystem, active_aliases: set[str]) -> None:
    """Overwrite the `active` component table so it exactly matches `active_aliases`.

    Rebuilt from scratch and overwritten (not merged) every call, since
    `registry.merge` only unions rows in and can't drop the tag from
    entities that left the radius. Safe to overwrite wholesale: `MapSystem`
    is the only writer of `active`.
    """
    data = {alias: ["active"] for alias in sorted(active_aliases)}
    new_registry = etl.execute(base_etl, input_dirs=[], yaml_strings={WORLD_FILE_ID: yaml.safe_dump(data, sort_keys=False)})
    registry.update({"active": new_registry.get("active").to_pyarrow()})
    new_registry.close()


def _player_alias(registry: Registry) -> str | None:
    """Return the current player entity's alias, or None if it doesn't exist yet."""
    if "character" not in registry.component_types:
        return None
    view = registry.view(["character.interaction_type"])
    df = view.filter(view["character.interaction_type"] == "player").execute()
    if df.empty:
        return None
    return df.iloc[0]["entity_id.alias"]


def _latest_positions(registry: Registry) -> pd.DataFrame:
    """Return one row per entity: its highest-turn `position`.

    `position` rows accumulate across turns rather than being overwritten
    (`registry.merge` only unions rows in; see `_merge_yaml_string`), so
    "current position" has to be resolved at read time instead of read
    directly off the table. Rows with no `turn` (e.g. hand-authored save
    files loaded without one) sort as oldest. Ties — including an entity
    with no `turn`-stamped row at all — are broken by keeping the last row
    in join order, mirroring `_latest_input`'s `.iloc[-1]` convention.
    """
    columns = ["entity_id", "entity_id.alias", "position.x", "position.y", "position.z", "position.turn"]
    if "position" not in registry.component_types:
        return pd.DataFrame(columns=columns)
    # `position`'s columns aren't schema-validated (no manifest_dir is wired
    # into the ETLSystem() this module uses), so a given merge's YAML may not
    # have mentioned every field (e.g. no `z`, or no `turn` on hand-authored
    # save data) — read the raw table and backfill absent fields as null
    # rather than assuming `registry.view` will find them.
    pos = registry.get("position").execute()
    for field in ("x", "y", "z", "turn"):
        if field not in pos.columns:
            pos[field] = None
    # entity_id.alias is for display only; the merge/groupby key below has to
    # be the actual entity_id, since aliases aren't guaranteed unique.
    aliases = registry.view(["entity_id.alias"]).execute()
    df = aliases.merge(pos[["entity_id", "x", "y", "z", "turn"]], on="entity_id")
    df = df.rename(columns={"x": "position.x", "y": "position.y", "z": "position.z", "turn": "position.turn"})
    sort_key = pd.to_numeric(df["position.turn"], errors="coerce").fillna(-1)
    df = df.iloc[sort_key.argsort(kind="stable")]
    return df.groupby("entity_id", as_index=False).tail(1)[columns]


def _player_position(registry: Registry) -> tuple[str, tuple[float, float]] | None:
    """Return (alias, (x, y)) for the player entity, or None if not known yet."""
    if "character" not in registry.component_types:
        return None
    if "position" not in registry.component_types:
        return None
    char_view = registry.view(["character.interaction_type"])
    try:
        char_df = char_view.filter(char_view["character.interaction_type"] == "player").execute()
    except KeyError:
        return None
    if char_df.empty:
        return None
    alias, entity_id = char_df.iloc[0]["entity_id.alias"], char_df.iloc[0]["entity_id"]
    positions = _latest_positions(registry)
    match = positions[positions["entity_id"] == entity_id]
    if match.empty:
        return None
    row = match.iloc[0]
    return alias, (float(row["position.x"]), float(row["position.y"]))


def _ensure_player_alias(registry: Registry, etl: ETLSystem) -> str:
    """Return the player entity's alias, seeding a minimal one if none exists yet.

    On the very first turn there's no player entity for InputSystem/
    ResolverAgentSystem to attach an `input` component to, since the
    Archivist only creates one once it transcribes the first exchange. Seed
    a bare `player` entity (matching the alias archivist.yaml already
    instructs the Archivist to use) so `input` always has somewhere to live.
    """
    alias = _player_alias(registry)
    if alias is not None:
        return alias
    data = {"player": [{"character": {"interaction_type": "player"}}]}
    _merge_yaml_string(registry, etl, WORLD_FILE_ID, yaml.safe_dump(data, sort_keys=False))
    return "player"


def _latest_input(registry: Registry, type_: str, turn: int) -> str | None:
    """Return the `type_`-authored input's text for `turn`, or None if not written yet.

    Without a validated schema loaded, iacs keeps field values as raw
    strings rather than casting `turn` to int, so the comparison is done on
    the string form of `turn` to stay dtype-agnostic.
    """
    if "input" not in registry.component_types:
        return None
    i = registry.get("input")
    df = i.filter(i.type == type_).execute()
    matches = df[df["turn"].astype(str) == str(turn)]
    if matches.empty:
        return None
    return matches.iloc[-1]["text"]


def _active_aliases(registry: Registry) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    if "active" not in registry.component_types:
        return set()
    view = registry.view("active")
    df = view.execute()
    return set(df["entity_id.alias"])


def _load_setting(path: Path = SETTING_CONFIG_PATH) -> str:
    """Return the world's setting text from `path` (see setting.yaml), or "" if unset."""
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("setting") or ""


def _build_prompt(
    text: str, active_aliases: set[str], setting: str = "", entity_details: str = ""
) -> str:
    """Assemble a turn's prompt from the world's setting, active entities, and the player's input.

    `setting` and `entity_details` are each folded in as their own
    out-of-character line/block, but only when non-empty, so a call with
    neither (the common case in tests) still reduces to the bare
    "Player input: ..." line it always has.
    """
    parts = []
    if setting:
        parts.append(f"World setting: {setting}")
    if active_aliases:
        parts.append(f"Active entities nearby: {', '.join(sorted(active_aliases))}")
    if entity_details:
        parts.append(f"Entity details:\n{entity_details}")
    if not parts:
        return text
    parts.append(f"Player input: {text}")
    return "\n".join(parts)
