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
import itertools
import math
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import ibis
import matplotlib
import numpy as np
import pandas as pd
import yaml
from iacs.dataflows import base_etl
from iacs.dataflows.etl import export_manifest
from iacs.etl_system import ETLSystem
from iacs.registry import Registry

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from story_simulator.config import ENVIRONMENT_ID, MANIFEST_DIR, PROD_AGENT_ID, resolve_anthropic_api_key
from story_simulator.mcp_client import open_iacs_mcp_session

WORLD_YAML_FILENAME = "world.yaml"
REGISTRY_DB_FILENAME = "registry.duckdb"
WORLD_FILE_ID = "world"
MAX_ARCHIVIST_TOOL_TURNS = 8
DEFAULT_ACTIVE_ENTITY_RADIUS = 20.0
DEFAULT_RENDER_PATH = Path("render.svg")
EC_FILE_GLOBS = ("*.yaml", "*.yml", "*.py", "*.csv")

PROD_RESOLVER_CONFIG_PATH = Path(__file__).parent / "resolver.yaml"
PROD_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.yaml"
TEST_ARCHIVIST_CONFIG_PATH = Path(__file__).parent / "archivist.test.yaml"


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
        new_registry = etl.execute(base_etl, input_dirs=[str(MANIFEST_DIR), *(str(f) for f in new_files)])
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

    The world's starting premise (the door, the empty expanse, the player)
    lives in `data/default/setting.yaml`, a hand-authored EC save file that
    `ETLLoaderSystem` loads into the registry, so it reaches the Resolver as
    an active entity. The hosted Agents/Sessions platform this System
    narrates through only accepts MCP servers reachable by URL, so it can't
    attach the local stdio `iacs-mcp` subprocess directly (see
    `ArchivistAgentSystem`); instead, this System talks to `iacs-mcp` itself
    as a plain MCP client (`_gather_entity_details`) to look up what's known
    about each active entity, and folds that into the prompt text.
    """

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
        entity_details = asyncio.run(self._gather_entity_details(Path(save_dir), _all_aliases(registry)))
        prompt = _build_prompt(command_text, active_aliases, entity_details=entity_details)
        response = self._respond(prompt)
        self.last_response = response

        alias = _ensure_player_alias(registry, etl)
        _add_input(registry, etl, alias, response, "agent", turn)

    async def _gather_entity_details(self, save_dir: Path, aliases: set[str]) -> str:
        """Ask the local iacs MCP server what's known about every entity in the world.

        Deliberately not scoped to just the `active` (nearby) tag: the
        Resolver has to reason about the destination of a described move
        (e.g. "walk 500 meters forward") before that destination's entities
        are anywhere near the player's *current* position, since `MapSystem`
        computes `active` from last turn's position and runs before this
        System each turn. Passing every entity's details, positions
        included, lets the Resolver work out spatially where a move lands
        and narrate what's actually there, while `active_aliases` (see
        `_build_prompt`) still tells it what's nearby right now for
        continuity. Only opens a session when there's something to look up,
        so a turn with no entities yet at all never pays for spawning the
        `iacs-mcp` subprocess.
        """
        if not aliases:
            return ""
        async with open_iacs_mcp_session(save_dir) as mcp:
            views = [
                await mcp.call_tool("view_entity", {"entity_id": alias})
                for alias in sorted(aliases)
            ]
        return "\n".join(views)

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
    disk. The registry itself (persisted via `Registry.from_database`) is
    the durable save, so `read_world_file`/`write_world_file` just
    read/write whatever the Archivist itself last wrote to disk; see
    `_export_world_yaml` for regenerating `world.yaml` from the registry
    on demand.

    Components
    ----------
    - todo: The docstrings are too verbose, explaining a lot of old context-specific
        reasoning. That's true for this entity and others.
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
        self._last_content = None
        asyncio.run(self._record_async(save_dir, command_text, narration_text))
        if self._last_content is not None:
            _merge_yaml_string(registry, etl, WORLD_FILE_ID, self._last_content, turn)

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

    def _write_world_file(self, save_dir: Path, content: str) -> str:
        """Write `content` to world.yaml, but only once it's parseable.

        `validate_yaml` is only ever *recommended* to the model, not
        required, and `step()` later feeds `self._last_content` straight
        into `etl.execute` (see `_merge_yaml_string`) with no validation of
        its own — so a single malformed write here would both corrupt the
        on-disk save (every subsequent turn's `ETLLoaderSystem` reloads it)
        and crash the very `step()` call that produced it. Checked with a
        bare `yaml.safe_load` rather than the fuller `validate_yaml` MCP
        tool: catching a syntax error is enough to avoid corrupting the
        file, and this doesn't require a round trip through the MCP session.
        """
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return f"Error: content is not valid YAML, nothing written. {e}"
        path = save_dir / WORLD_YAML_FILENAME
        path.write_text(content)
        self._last_content = content
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
            annotations = [
                ax.annotate(
                    row["entity_id.alias"],
                    xy=(row["position.x"], row["position.y"]),
                    xytext=_offset_data_point(ax, (row["position.x"], row["position.y"]), 5, 5),
                    textcoords="data",
                    arrowprops=dict(arrowstyle="-", color="0.5", linewidth=0.5, shrinkA=0, shrinkB=2),
                )
                for _, row in df.iterrows()
            ]
            _avoid_overlapping_labels(fig, ax, annotations)
            _expand_limits_to_fit_labels(fig, ax, annotations)
        ax.set_aspect("equal", adjustable="datalim")
        # bbox_inches="tight": a label nudged clear of an overlap can land
        # further from its point than the figure's fixed canvas allows,
        # otherwise clipping it at the image edge instead of just avoiding
        # the overlap it was pushed away from.
        fig.savefig(self.render_path, bbox_inches="tight")
        plt.close(fig)


def _offset_data_point(ax, xy: tuple[float, float], dx_pts: float, dy_pts: float) -> tuple[float, float]:
    """Convert a (dx_pts, dy_pts) offset in points into a nearby data-coordinate point.

    Lets label placement start from the same "a few points up and to the
    right" position the old `textcoords="offset points"` annotations used,
    while keeping every subsequent move in data coordinates so
    `_avoid_overlapping_labels` can freely reposition labels via `xyann`.
    """
    origin_px = ax.transData.transform(xy)
    points_to_px = ax.figure.dpi / 72.0
    shifted_px = origin_px + np.array([dx_pts, dy_pts]) * points_to_px
    return tuple(ax.transData.inverted().transform(shifted_px))


def _avoid_overlapping_labels(fig, ax, annotations: list, max_iterations: int = 60, padding_px: float = 2.0) -> None:
    """Nudge annotation labels apart, in place, until their bounding boxes stop overlapping.

    Each pass measures every label's on-screen bounding box once (via the
    renderer) and, for every overlapping pair found in that snapshot, pushes
    both labels apart along whichever single axis (x or y) has the smaller
    penetration — the standard minimum-translation-vector fix for two
    overlapping boxes. Pushing along one axis at a time (rather than both,
    which is what a naive read of "overlap" suggests) keeps each correction
    to the least displacement that actually clears it; pushing both axes at
    once was found to compound diagonally across many mutually-overlapping
    labels and fling some of them far off into empty space while others
    stayed stuck. Measuring once per pass rather than re-measuring after
    every individual nudge is deliberate: `get_window_extent`'s font-metrics
    work is the dominant cost here, and re-measuring per-nudge turns a dense
    cluster (where most of the O(labels^2) pairs overlap at once) into an
    O(labels^3)-ish worst case — dozens of labels stacked on the same point
    was observed to take minutes rather than seconds. Repeats because
    resolving one pair can create or reveal an overlap elsewhere; stops as
    soon as a pass makes no moves, or after `max_iterations` as a safety cap
    that bounds worst-case cost for pathological/dense layouts (leaving a
    few such labels still overlapping is preferable to a multi-second stall
    once a turn).
    """
    if len(annotations) < 2:
        return
    # One draw suffices to obtain a renderer: `get_window_extent(renderer)`
    # recomputes each label's bbox from its *current* position and the
    # renderer's font metrics on every call, so re-measuring after a nudge
    # doesn't require redrawing the whole figure (scatter points, axes,
    # arrows, ...) on every one of up to `max_iterations` passes.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for _ in range(max_iterations):
        boxes = [annotation.get_window_extent(renderer) for annotation in annotations]
        moved = False
        for i, j in itertools.combinations(range(len(annotations)), 2):
            bi, bj = boxes[i], boxes[j]
            overlap_x = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
            overlap_y = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
            if overlap_x <= 0 or overlap_y <= 0:
                continue
            moved = True
            dx = (bj.x0 + bj.x1) - (bi.x0 + bi.x1)
            dy = (bj.y0 + bj.y1) - (bi.y0 + bi.y1)
            if overlap_x <= overlap_y:
                sign = 1.0 if dx > 0 else (-1.0 if dx < 0 else (1.0 if j > i else -1.0))
                push = sign * (overlap_x / 2 + padding_px)
                _nudge_label(ax, annotations[i], -push, 0.0)
                _nudge_label(ax, annotations[j], push, 0.0)
            else:
                sign = 1.0 if dy > 0 else (-1.0 if dy < 0 else (1.0 if j > i else -1.0))
                push = sign * (overlap_y / 2 + padding_px)
                _nudge_label(ax, annotations[i], 0.0, -push)
                _nudge_label(ax, annotations[j], 0.0, push)
        if not moved:
            return


def _nudge_label(ax, annotation, dx_px: float, dy_px: float) -> None:
    """Shift an annotation's text position by a pixel offset, keeping it in data coordinates."""
    current_px = ax.transData.transform(annotation.xyann)
    annotation.xyann = tuple(ax.transData.inverted().transform(current_px + np.array([dx_px, dy_px])))


def _expand_limits_to_fit_labels(fig, ax, annotations: list) -> None:
    """Grow the axes' view limits so every (possibly repositioned) label stays visible.

    Text isn't included in matplotlib's autoscaling, so a label
    `_avoid_overlapping_labels` pushed toward a dense cluster's edge can end
    up outside the view the scatter points alone would produce, clipping it
    out of the render entirely. Feeding each label's data-space bounding box
    into `update_datalim` lets `autoscale_view` widen the limits to include
    them, the same way it already accounts for the plotted points.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    corners = []
    for annotation in annotations:
        bbox = annotation.get_window_extent(renderer)
        corners.append(inv.transform((bbox.x0, bbox.y0)))
        corners.append(inv.transform((bbox.x1, bbox.y1)))
    ax.update_datalim(corners)
    ax.autoscale_view()


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
    new_registry = etl.execute(base_etl, input_dirs=[str(MANIFEST_DIR)], yaml_strings={key: yaml_text})
    if turn is not None and "position" in new_registry.component_types:
        # Cast explicitly: a bare ibis.literal(turn) infers the smallest
        # integer type that fits the value (int8 for small turn numbers),
        # which conflicts with the schema-validated int64 "turn" column on
        # any row already in the registry once `registry.merge`'s union
        # tries to combine them.
        stamped = new_registry.get("position").mutate(turn=ibis.literal(turn).cast("int64"))
        new_registry.update({"position": stamped})
    _reconcile_entity_ids(registry, new_registry)
    registry.merge(new_registry)
    new_registry.close()


def _reconcile_entity_ids(registry: Registry, new_registry: Registry) -> None:
    """Remap `new_registry`'s entity_ids onto `registry`'s existing ones, by alias.

    `entity_id` is derived as a hash of `(file_id, entity_path)` (see
    `iacs.dataflows.etl.load_manifest.entity_id_table`), so writing the same
    alias (e.g. "player") from a different source than it was first recorded
    under — the Archivist's synthetic "world" YAML vs. a hand-authored
    `setting.yaml` — mints a *different* id for what's meant to be the same
    entity, rather than updating it. Left unreconciled, `registry.merge`
    unions both in as separate entities that happen to share an alias:
    `entity_id.alias`-joined reads that don't also constrain by entity_id
    (e.g. `Registry.view_current`, which groups by entity_id alone) then see
    two independent "current" rows for what should be one entity.

    Since `alias` is the stable, author-facing identity that's meant to carry
    across sources (unlike the source-derived hash), any incoming entity
    whose alias matches an entity already in `registry` is remapped onto that
    existing id in place, before `new_registry` is merged in.
    """
    if "entity_id" not in registry.component_types or "entity_id" not in new_registry.component_types:
        return
    existing = registry.get("entity_id").execute()
    incoming = new_registry.get("entity_id").execute()
    mapping = {}
    for _, row in incoming.iterrows():
        match = existing.loc[existing["alias"] == row["alias"], "value"]
        if not match.empty and match.iloc[0] != row["value"]:
            mapping[row["value"]] = match.iloc[0]
    if not mapping:
        return
    for comp_type in new_registry.component_types:
        table = new_registry.get(comp_type).execute()
        if comp_type == "entity_id":
            # Drop the now-superseded rows outright rather than remapping
            # their own "value" column: the canonical row for this alias is
            # already present in `registry` and merging in a second row under
            # the same alias (even pointed at the same id) would leave two
            # `entity_id` rows per alias, breaking any lookup that expects
            # exactly one (e.g. `_entity_id_for_alias`'s `.iloc[0]`).
            table = table[~table["value"].isin(mapping)]
        elif "entity_id" in table.columns:
            table["entity_id"] = table["entity_id"].replace(mapping)
        else:
            continue
        new_registry.update({comp_type: table})


def _export_world_yaml(registry: Registry, etl: ETLSystem, save_dir: Path) -> None:
    """Regenerate `world.yaml` as a human/AI-readable export of the registry's state.

    Purely a derived artifact — the registry (persisted via
    `Registry.to_database`/`Registry.from_database`) is the actual save
    data, and nothing reads this file back in. Written via iacs's own
    `export_manifest` dataflow, which writes one output file per original
    source identifier; every direct registry merge in this module uses
    `WORLD_FILE_ID` ("world"), which `export_manifest` suffixes into
    `world.yaml`.

    A standalone utility, not part of the per-turn System pipeline:
    `export_manifest` has no notion of this project's own `manifest/`
    schema entities being "builtins" the way iacs's bundled ones are, so
    calling this every turn would also dump a stray copy of `manifest/`
    into `save_dir`. Intended for an explicit/user-triggered export.
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


def _entity_id_for_alias(registry: Registry, alias: str) -> str | None:
    """Look up `alias`'s existing entity_id hash, or None if it's not known yet.

    Used to pin a synthetic `WORLD_FILE_ID` YAML write onto an entity's
    *existing* identity (see `_add_input`/`_sync_active_tags`) instead of
    minting a fresh one, which `iacs.dataflows.etl.load_manifest.entity_id_overrides`
    supports via a bare `{entity_id: <hash>}` component.
    """
    if "entity_id" not in registry.component_types:
        return None
    eids = registry.get("entity_id").execute()
    match = eids.loc[eids["alias"] == alias, "value"]
    return match.iloc[0] if not match.empty else None


def _add_input(registry: Registry, etl: ETLSystem, alias: str, text: str, type_: str, turn: int) -> None:
    """Merge a new `input` component instance onto `alias`'s entity.

    Rebuilds and overwrites the whole `input` component table from
    `alias`'s full history plus the new instance, rather than unioning in
    just the new row — `registry.merge` would otherwise collide every call
    on the same `component_index` (each call's YAML fragment is its own
    single-item list, always indexed 0). Safe to overwrite wholesale: only
    `InputSystem`/`ResolverAgentSystem` ever write `input`, and always onto
    the one player entity.

    Pins the write onto `alias`'s existing entity_id (see
    `_entity_id_for_alias`) whenever one is already known — e.g. the player
    entity from a hand-authored `setting.yaml` — rather than the fresh
    identity a plain `{alias: [...]}` YAML fragment would otherwise mint
    under this call's own synthetic "world" source. Without that override,
    `_input_history`'s `entity_id.alias`-joined read would never find this
    row (its entity_id has no matching `entity_id` table entry, since
    `registry.update` below only overwrites `input`, not `entity_id`),
    silently losing the just-written instance the next time history is
    rebuilt.
    """
    history = _input_history(registry, alias) + [{"text": text, "type": type_, "turn": turn}]
    entries = [{"input": h} for h in history]
    entity_id = _entity_id_for_alias(registry, alias)
    if entity_id is not None:
        entries = [{"entity_id": entity_id}] + entries
    data = {alias: entries}
    new_registry = etl.execute(
        base_etl, input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml.safe_dump(data, sort_keys=False)}
    )
    # .to_pyarrow() materializes the data so it can cross from new_registry's
    # connection into registry's (mirrors Registry.merge's own approach).
    registry.update({"input": new_registry.get("input").to_pyarrow()})
    new_registry.close()


def _sync_active_tags(registry: Registry, etl: ETLSystem, active_aliases: set[str]) -> None:
    """Overwrite the `active` component table so it exactly matches `active_aliases`.

    Each alias's `active` tag is declared alongside an explicit `entity_id`
    override (see `_entity_id_for_alias`) so it lands on that alias's
    existing entity rather than a fresh identity disconnected from it — see
    `_add_input`'s docstring for why that matters for `entity_id.alias`-joined
    reads (here, `_active_aliases`'s `view("active")`).

    Rebuilt from scratch and overwritten (not merged) every call, since
    `registry.merge` only unions rows in and can't drop the tag from
    entities that left the radius. Safe to overwrite wholesale: `MapSystem`
    is the only writer of `active`.
    """
    data = {
        alias: [{"entity_id": _entity_id_for_alias(registry, alias)}, "active"]
        for alias in sorted(active_aliases)
    }
    new_registry = etl.execute(
        base_etl, input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml.safe_dump(data, sort_keys=False)}
    )
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
    directly off the table. Delegated to `Registry.view_current`, which
    resolves this the same way for any component with a field flagged
    `time_dimension: true` — see `turn`'s definition in
    `manifest/builtins.yaml` — rather than reimplementing that resolution
    by hand here.
    """
    columns = ["entity_id", "entity_id.alias", "position.x", "position.y", "position.z", "position.turn"]
    if "position" not in registry.component_types:
        return pd.DataFrame(columns=columns)
    return registry.view_current(["position.x", "position.y", "position.z", "position.turn"]).execute()[columns]


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

    `input.turn` is schema-validated (type: int) by every ETL call that
    produces it, so `turn` is compared directly rather than coercing to
    string.
    """
    if "input" not in registry.component_types:
        return None
    i = registry.get("input")
    df = i.filter(i.type == type_).execute()
    matches = df[df["turn"] == turn]
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


def _all_aliases(registry: Registry) -> set[str]:
    """Return the aliases of every entity known to the registry."""
    if "entity_id" not in registry.component_types:
        return set()
    return set(registry.get("entity_id").execute()["alias"])


def _build_prompt(text: str, active_aliases: set[str], entity_details: str = "") -> str:
    """Assemble a turn's prompt from the active entities, their details, and the player's input.

    `entity_details` is folded in as its own out-of-character block, but only
    when non-empty, so a call without it (the common case in tests) still
    reduces to the same "Active entities nearby: .../Player input: ..." shape
    this always had.
    """
    parts = []
    if active_aliases:
        parts.append(f"Active entities nearby: {', '.join(sorted(active_aliases))}")
    if entity_details:
        parts.append(f"Entity details:\n{entity_details}")
    if not parts:
        return text
    parts.append(f"Player input: {text}")
    return "\n".join(parts)
