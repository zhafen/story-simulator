"""ECS-style Systems that drive an EnsembleWorld's turn loop.

Every turn, `EnsembleWorld` calls `step()` on each `System` in a fixed order.
Systems never call each other directly or pass return values between one
another; instead they communicate exclusively through the iacs `Registrar`
(a shared, long-lived object every System reads and mutates directly, per
`Registrar`'s own "user-facing interface to a registry" role), so every
value lives on the entity that produced it: the player entity owns `input`
components (its own commands and the Resolver's narrated replies,
distinguished by `type`), and each nearby character/object owns a bare
`active` tag for the turn. `ETLLoaderSystem` runs first each turn to pick up
any EC files in `save_dir` that nothing has fed into the registrar yet.
`world.yaml`, if present in `save_dir`, is only ever a derived,
human/AI-readable export of the registrar (see `_export_world_yaml`) —
nothing writes it as part of the per-turn pipeline, and nothing reads it
back in as authoritative; the actual save data is the registrar's registry,
persisted via `Registrar.save`/`Registrar.load`.
"""

import asyncio
import itertools
import math
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic
import matplotlib
import numpy as np
import pandas as pd
import yaml
from iacs.registrar import Registrar

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
PROD_NPC_CONFIG_PATH = Path(__file__).parent / "npc.yaml"


class System(ABC):
    """One stage of an EnsembleWorld turn."""

    @abstractmethod
    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        raise NotImplementedError


class ETLLoaderSystem(System):
    """Loads any not-yet-loaded EC files from `save_dir` into the registrar.

    Runs first each turn so every other System sees the latest on-disk
    state. Tracks every file path already merged in `loaded_files`, so a
    file is loaded exactly once. `world.yaml` is always skipped: it's a
    derived export of the registrar (see `_export_world_yaml`), not an
    independent source, and reloading it would mint duplicate entities under
    a different file identifier than the `WORLD_FILE_ID` every direct
    registrar update already uses. This System exists to pick up files
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

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
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
        registrar.update(input_dirs=[str(MANIFEST_DIR), *(str(f) for f in new_files)])
        self.loaded_files.update(new_files)


class InputSystem(System):
    """Registers the player's raw input as an `input` component on the player entity."""

    def __init__(self):
        self._pending_text: str | None = None

    def receive(self, text: str) -> None:
        """Queue the player's raw text for the next step() call."""
        self._pending_text = text

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        if save_dir is None or self._pending_text is None:
            return
        alias = _ensure_player_alias(registrar)
        _add_input(registrar, alias, self._pending_text, "player", turn)
        self._pending_text = None


class AgentSystem(System, ABC):
    """Base class for Systems whose step() calls out to an Anthropic agent.

    Components
    ----------
    - todo: Why have this defined here, instead of adjacent to the agent systems?
    """


class MapSystem(System):
    """Tags characters/objects within `radius` of the reference character as `active` for the turn.

    The reference character is normally the player, but falls back to the
    sole character present when there's no player (see `_player_position`),
    so an NPC-only world still gets an `active` set to narrate/decide from.

    Reads the reference character's position as of the *previous* turn's
    recorded data (this System runs before `InputSystem`/`NPCAgentSystem`/
    `ResolverAgentSystem` each turn), and adds/removes a bare `active` tag
    directly on each entity as it enters or leaves range. Also merges every
    active entity into the reference character's permanent `memory` relation
    (see `_record_memory`) — unlike `active`, `memory` is never cleared, so
    it's what scopes an NPC's decision-making agent to what it has actually
    encountered rather than the whole registry.

    Components
    ----------
    - todo: Reincorporate z-axis.
    """

    def __init__(self, radius: float = DEFAULT_ACTIVE_ENTITY_RADIUS):
        self.radius = radius

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        reference = _player_position(registrar)
        if reference is None:
            return
        reference_alias, reference_pos = reference
        # entity_id.alias is left out here: label_df (below) already carries its
        # own copy via registrar.view(), and merging on entity_id would otherwise
        # produce two colliding entity_id.alias columns.
        positions = _latest_positions(registrar)[["entity_id", "position.x", "position.y"]]

        active_aliases = set()
        for component, label_field in (("character", "interaction_type"), ("object", "type")):
            label_df = _safe_view(registrar, f"{component}.{label_field}")
            if label_df is None:
                continue
            for _, row in label_df.merge(positions, on="entity_id").iterrows():
                alias = row["entity_id.alias"]
                if alias == reference_alias:
                    continue
                pos = (float(row["position.x"]), float(row["position.y"]))
                if math.dist(pos, reference_pos) <= self.radius:
                    active_aliases.add(alias)

        _sync_active_tags(registrar, active_aliases)
        _record_memory(registrar, reference_alias, active_aliases)


class NPCAgentSystem(AgentSystem):
    """Generates an NPC character's command for the turn via a lightweight decision agent.

    Mirrors InputSystem's role for the player — attaching a fresh
    "player"-type `input` component onto the acting entity for
    ResolverAgentSystem to consume — but the text comes from an agent's
    decision instead of a human's typed command. This is the concrete form
    of "NPCs use the same interface as players, just agent-sourced text":
    both InputSystem and NPCAgentSystem feed the identical `_add_input(...,
    "player", turn)` call, and ResolverAgentSystem/ArchivistAgentSystem don't
    know or care which one produced a given turn's command.

    Scoped to what the NPC has actually perceived — `active` union `memory`
    (see MapSystem) — plus its own `agenda`, rather than the whole registry.
    Runs a single non-streaming `messages.create` call directly against this
    System's own registrar, unlike ResolverAgentSystem, which narrates
    through the hosted Agents/Sessions platform and so has no local registrar
    access of its own.

    Only one character is expected to act per turn — the same assumption
    ResolverAgentSystem/ArchivistAgentSystem already make by resolving a
    single command per turn (see their docstrings) — so this sits the turn
    out once a command already exists (from a human player, most commonly),
    and otherwise always picks the alphabetically-first NPC when there's more
    than one; a mixed multi-NPC world resolving every NPC's command in the
    same turn would need Resolver/Archivist to loop too, which is out of
    scope for the single-NPC worlds this currently supports.
    """

    def __init__(self, config_path: Path = PROD_NPC_CONFIG_PATH):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        config = yaml.safe_load(config_path.read_text())
        self.model = config["model"]
        self.system = config["system"]

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        if _latest_input(registrar, "player", turn) is not None:
            return
        npc_aliases = _npc_aliases(registrar)
        if not npc_aliases:
            return
        alias = npc_aliases[0]
        command = self._decide(registrar, alias)
        _add_input(registrar, alias, command, "player", turn)

    def _decide(self, registrar: Registrar, alias: str) -> str:
        prompt = _build_npc_prompt(registrar, alias)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


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

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        command_text = _latest_input(registrar, "player", turn)
        if command_text is None:
            return

        # Whichever character actually acted this turn (the human player, or
        # an NPC via NPCAgentSystem) — falling back to "player" only for the
        # degenerate case of a command recorded with no character entity
        # behind it at all, which shouldn't happen via
        # InputSystem/NPCAgentSystem.
        actor_alias = _acting_character_alias(registrar, turn) or "player"
        active_aliases = _active_aliases(registrar)
        entity_details = asyncio.run(self._gather_entity_details(Path(save_dir), _all_aliases(registrar)))
        prompt = _build_prompt(actor_alias, command_text, active_aliases, entity_details=entity_details)
        response = self._respond(prompt)
        self.last_response = response

        alias = _acting_character_alias(registrar, turn) or _ensure_player_alias(registrar)
        _add_input(registrar, alias, response, "agent", turn)

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
    transport (`open_iacs_mcp_session`) is itself async-only. Alongside the
    iacs MCP server's tools (describe_format, validate_yaml, ...), the model
    is given two local tools backed directly by this turn's own `registrar`:
    `view_registry` (`Registrar.view_df(...).to_csv()`) to see what's already
    recorded, and `update_registry` (a thin wrapper over `_merge_yaml_string`,
    itself built on `Registrar.update`) to merge in new or changed entities.
    Both read/write the exact same registrar every other System uses —
    there's no separate on-disk save file for the Archivist to keep in sync
    with it, so nothing to reconcile afterward.

    Components
    ----------
    - todo: The docstrings are too verbose, explaining a lot of old context-specific
        reasoning. That's true for this entity and others.
    """

    def __init__(self, config_path: Path = PROD_ARCHIVIST_CONFIG_PATH):
        self.client = anthropic.Anthropic(api_key=resolve_anthropic_api_key())
        config = yaml.safe_load(config_path.read_text())
        if not config.get("system"):
            config["system"] = yaml.safe_load(PROD_ARCHIVIST_CONFIG_PATH.read_text())["system"]
        self.model = config["model"]
        self.system = config["system"]

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        command_text = _latest_input(registrar, "player", turn)
        narration_text = _latest_input(registrar, "agent", turn)
        if command_text is None or narration_text is None:
            return
        # Whichever character actually acted this turn — the human player, or
        # an NPC via NPCAgentSystem — falling back to "player" only for the
        # degenerate case _acting_character_alias itself falls back for (see
        # ResolverAgentSystem.step).
        actor_alias = _acting_character_alias(registrar, turn) or "player"
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        asyncio.run(self._record_async(registrar, save_dir, actor_alias, command_text, narration_text, turn))

    async def _record_async(
        self,
        registrar: Registrar,
        save_dir: Path,
        actor_alias: str,
        player_input: str,
        world_response: str,
        turn: int,
    ) -> None:
        async with open_iacs_mcp_session(save_dir) as mcp:
            tools = mcp.tools + [_VIEW_REGISTRY_TOOL, _UPDATE_REGISTRY_TOOL]
            messages = [
                {"role": "user", "content": self._build_prompt(actor_alias, player_input, world_response)}
            ]
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
                    result_text = await self._dispatch_tool(mcp, registrar, turn, block.name, block.input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                    )
                messages.append({"role": "user", "content": tool_results})

    @staticmethod
    def _build_prompt(actor_alias: str, player_input: str, world_response: str) -> str:
        """Build the transcription prompt, naming the acting character by their own alias.

        Deliberately says "{actor_alias}'s command", not "Player input" — the
        acting character isn't always the player (see NPCAgentSystem), and a
        literal "Player input" line was observed to make the Archivist invent
        a brand-new "player" entity from scratch in an NPC-only world instead
        of recognizing the actor already in the registry, since it had no
        entity to resolve that wording against.
        """
        return (
            f"{actor_alias}'s command: {player_input}\n"
            f"World response: {world_response}\n\n"
            "Transcribe any entities/components this exchange reveals or changes "
            "into the world registry."
        )

    async def _dispatch_tool(
        self, mcp, registrar: Registrar, turn: int, name: str, arguments: dict
    ) -> str:
        """Dispatch one tool call, converting any exception into an error string.

        Mirrors what an MCP server already does for its own tools (e.g. the
        `mcp.call_tool` fallback below): FastMCP catches an exception raised
        inside a `@server.tool()` function and returns it as that tool's
        result rather than letting it propagate. This local loop has no such
        safety net of its own, so a bad argument (an unknown component_type,
        malformed `update_registry` YAML, ...) would otherwise crash the
        whole turn instead of giving the model something it can read and
        retry from. Deliberately just one broad `except`, not a bespoke
        pre-check per tool: `_merge_yaml_string`'s own YAML parsing (via
        `Registrar.update`) already raises a perfectly readable
        `yaml.YAMLError` on malformed content, so there's nothing a separate
        `yaml.safe_load` pre-check here would add beyond what running the
        real thing and catching its failure already gives for free.
        """
        try:
            if name == "view_registry":
                return registrar.view_df(arguments["component_type"]).to_csv()
            if name == "update_registry":
                _merge_yaml_string(registrar, WORLD_FILE_ID, arguments["yaml_string"], turn)
                return "Merged into the registry."
            return await mcp.call_tool(name, arguments)
        except Exception as e:
            return f"Error: {e}"


class VisualizerSystem(System):
    """Renders an SVG scatter plot of every positioned entity, each turn."""

    def __init__(self, render_path: Path = DEFAULT_RENDER_PATH):
        self.render_path = Path(render_path)

    def step(self, registrar: Registrar, save_dir: Path | None, turn: int) -> None:
        if save_dir is None:
            return
        df = _latest_positions(registrar)

        fig, ax = plt.subplots()
        if not df.empty:
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


_VIEW_REGISTRY_TOOL = {
    "name": "view_registry",
    "description": (
        "View all recorded data for one component type (e.g. \"position\", "
        "\"object\", \"character\") directly from the world registry — "
        "covers both the starting scenario and anything recorded in prior "
        "turns, so entities already known can be added to rather than "
        "duplicated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "component_type": {
                "type": "string",
                "description": "The component type to view, e.g. \"position\".",
            },
        },
        "required": ["component_type"],
    },
}

_UPDATE_REGISTRY_TOOL = {
    "name": "update_registry",
    "description": (
        "Merge entity-first YAML into the world registry, run through the "
        "same ETL pipeline used to load save files."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "yaml_string": {
                "type": "string",
                "description": "Entity-first YAML content to merge in.",
            },
        },
        "required": ["yaml_string"],
    },
}


def _merge_yaml_string(
    registrar: Registrar, key: str, yaml_text: str, turn: int | None = None
) -> None:
    """Run the ETL pipeline on a raw YAML string and merge the result into `registrar`.

    If `turn` is given, it's forwarded as `Registrar.update`'s `time`, which
    backfills any still-null field flagged `time_dimension: true` — here,
    `position.turn` (see `manifest/builtins.yaml`) — rather than this
    function stamping it in by hand. Unlike `input` (whose `turn` is set
    explicitly by `_add_input`), `position` is written from the Archivist's
    freeform YAML, which has no reason to know about the turn counter, so
    it's filled in here instead. `position` rows accumulate across turns
    rather than being overwritten (merging only unions rows in), so this
    `turn` column is what lets readers resolve which row is current; see
    `_latest_positions`.

    Called directly on `registrar` (not a throwaway one merged in
    afterward): `yaml_text` attaching to an entity that already exists —
    e.g. the player, or "journaling_desk.desk" — rather than minting a
    fresh, disconnected one under this call's own synthetic "world" source
    is handled by a `same_as` component in `yaml_text` itself (iacs's own
    mechanism for this; see `iacs.dataflows.derive.resolve_same_as`), which
    only resolves against entities `registrar` already has because
    `Registrar.update` passes its own registry through as
    `existing_registry`. A separately-built registrar has no such
    visibility, so there's nothing left for this function to reconcile by
    hand afterward the way it used to.
    """
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={key: yaml_text}, time=turn)


def _export_world_yaml(registrar: Registrar, save_dir: Path) -> None:
    """Regenerate `world.yaml` as a human/AI-readable export of the registrar's registry.

    Purely a derived artifact — the registrar's registry (persisted via
    `Registrar.save`/`Registrar.load`) is the actual save data, and nothing
    reads this file back in. Written via `Registrar.export_manifest`, which
    writes one output file per original source identifier; every direct
    registrar update in this module uses `WORLD_FILE_ID` ("world"), which
    `export_manifest` suffixes into `world.yaml`.

    A standalone utility, not part of the per-turn System pipeline:
    `export_manifest` has no notion of this project's own `manifest/`
    schema entities being "builtins" the way iacs's bundled ones are, so
    calling this every turn would also dump a stray copy of `manifest/`
    into `save_dir`. Intended for an explicit/user-triggered export.
    """
    registrar.export_manifest(output_dir=str(save_dir))


def _safe_view(registrar: Registrar, fields: str | list[str]) -> pd.DataFrame | None:
    """Execute `registrar.view(fields)`, or None if that data isn't there yet.

    iacs declares a component type's schema (see `Registry.declare_schema`)
    as soon as any update loads the manifest that defines it, letting
    `Registrar.view`/`.get` return an empty, correctly-typed result for a
    declared-but-dataless type instead of raising — but a registrar that
    hasn't run any update yet (e.g. a bare `Registrar()`, before even
    `MANIFEST_DIR` has been merged in) has no declared schemas at all, not
    even for `entity_id` itself. Every reader below can be called at exactly
    that point (before the first turn's Archivist write, before `MapSystem`
    has ever run), so a missing component type still isn't an error here.
    """
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view(fields).execute()
    except KeyError:
        return None


def _safe_get(registrar: Registrar, component_type: str) -> pd.DataFrame | None:
    """Execute `registrar.get(component_type)`, or None if it's not loaded yet.

    The `.get()` counterpart to `_safe_view`, for the few readers that want
    the raw component table (no `entity_id.alias` join) rather than a view.
    """
    if component_type not in registrar.registry.component_types:
        return None
    return registrar.get(component_type).execute()


def _add_input(registrar: Registrar, alias: str, text: str, type_: str, turn: int) -> None:
    """Merge a new `input` component instance onto `alias`'s existing entity.

    A `same_as` component (see `_merge_yaml_string`) attaches the new
    instance onto `alias`'s existing entity — e.g. the player entity from a
    hand-authored `setting.yaml` — rather than minting a fresh, disconnected
    one under this call's own synthetic "world" source. Declared under a
    throwaway `{alias}_update` entity key, not `alias` itself: `same_as`
    resolution excludes the owner from its own candidate search, so if the
    owner's key hashed to the exact same identity as its target (which
    happens whenever `alias` already exists only because an earlier call
    here created it, since every such write shares this same synthetic
    "world" source and entity_path == alias), zero *other* candidates would
    be left to resolve to and iacs would reject it as unresolvable — giving
    the owner a distinct key sidesteps that regardless of where the target
    came from.

    Merged in directly rather than rebuilt from scratch (unlike `active`;
    see `_sync_active_tags`), since `input` is meant to accumulate every
    turn's exchange, not be replaced. Separate calls' rows sharing a
    component_index (each call's YAML fragment is its own single-item list,
    always indexed 0 relative to itself) is fine — the same way
    `Registry.view_current` already tolerates that for accumulated
    `position` rows — since nothing reads `input` by component_index.
    """
    data = {
        f"{alias}_update": [
            {"same_as": {"value": alias}},
            {"input": {"text": text, "type": type_, "turn": turn}},
        ]
    }
    _merge_yaml_string(registrar, WORLD_FILE_ID, yaml.safe_dump(data, sort_keys=False))


def _sync_active_tags(registrar: Registrar, active_aliases: set[str]) -> None:
    """Overwrite the `active` component table so it exactly matches `active_aliases`.

    A merge can only union rows in, never drop the tag from an entity that
    left the radius, so the existing `active` table (if any) is cleared
    first — via `Registrar.overwrite`, to an empty table of its own schema,
    safe since `MapSystem` is the only writer of `active` — and the current
    set is merged back in via `same_as` (see `_merge_yaml_string`),
    attaching each tag onto its alias's existing entity rather than a fresh,
    disconnected one. Declared under a throwaway `{alias}_update` entity key
    for each alias, not the alias itself — see `_add_input`'s docstring for
    why that's needed for `same_as` resolution to succeed regardless of
    where the target entity originally came from.
    """
    if "active" in registrar.registry.component_types:
        registrar.overwrite("active", registrar.get("active").limit(0).to_pyarrow())
    if not active_aliases:
        return
    data = {
        f"{alias}_update": [{"same_as": {"value": alias}}, "active"] for alias in sorted(active_aliases)
    }
    _merge_yaml_string(registrar, WORLD_FILE_ID, yaml.safe_dump(data, sort_keys=False))


def _player_alias(registrar: Registrar) -> str | None:
    """Return the current player entity's alias, or None if it doesn't exist yet."""
    df = _safe_view(registrar, "character.interaction_type")
    if df is None:
        return None
    df = df[df["character.interaction_type"] == "player"]
    if df.empty:
        return None
    return df.iloc[0]["entity_id.alias"]


def _latest_positions(registrar: Registrar) -> pd.DataFrame:
    """Return one row per entity: its highest-turn `position`.

    `position` rows accumulate across turns rather than being overwritten
    (merging only unions rows in; see `_merge_yaml_string`), so "current
    position" has to be resolved at read time instead of read directly off
    the table. Delegated to `Registrar.view_current`, which resolves this
    the same way for any component with a field flagged `time_dimension:
    true` — see `turn`'s definition in `manifest/builtins.yaml` — rather
    than reimplementing that resolution by hand here.
    """
    columns = ["entity_id", "entity_id.alias", "position.x", "position.y", "position.z", "position.turn"]
    if "position" not in registrar.registry.component_types:
        return pd.DataFrame(columns=columns)
    return registrar.view_current(["position.x", "position.y", "position.z", "position.turn"]).execute()[columns]


def _player_position(registrar: Registrar) -> tuple[str, tuple[float, float]] | None:
    """Return (alias, (x, y)) for MapSystem's reference character, or None if not known yet.

    Prefers the character with `interaction_type == "player"`, the common
    case every existing player-driven world hits. Falls back to the sole
    character present when there's no player at all — an NPC-only world
    (e.g. tests/data/settings/npc) still needs a reference point to compute
    `active`/`memory` from. With more than one character and no player,
    there's no unambiguous reference character, so this returns None (same
    as "not known yet") rather than guessing.
    """
    char_df = _safe_view(registrar, "character.interaction_type")
    if char_df is None:
        return None
    player_df = char_df[char_df["character.interaction_type"] == "player"]
    if not player_df.empty:
        row = player_df.iloc[0]
    elif len(char_df) == 1:
        row = char_df.iloc[0]
    else:
        return None
    alias, entity_id = row["entity_id.alias"], row["entity_id"]
    positions = _latest_positions(registrar)
    match = positions[positions["entity_id"] == entity_id]
    if match.empty:
        return None
    row = match.iloc[0]
    return alias, (float(row["position.x"]), float(row["position.y"]))


def _npc_aliases(registrar: Registrar) -> list[str]:
    """Return the aliases of every `interaction_type == "npc"` character, sorted."""
    df = _safe_view(registrar, "character.interaction_type")
    if df is None:
        return []
    df = df[df["character.interaction_type"] == "npc"]
    return sorted(df["entity_id.alias"])


def _memory_aliases(registrar: Registrar, owner_alias: str) -> set[str]:
    """Return every alias `owner_alias` has ever perceived (see MapSystem's `memory` writes)."""
    df = _safe_view(registrar, "memory.value")
    if df is None:
        return set()
    return set(df[df["entity_id.alias"] == owner_alias]["memory.value"])


def _record_memory(registrar: Registrar, owner_alias: str, perceived_aliases: set[str]) -> None:
    """Merge `perceived_aliases` into `owner_alias`'s permanent `memory` relation.

    Called every turn with just that turn's `active_aliases` (not the
    accumulated set) — merging only ever unions rows in (see
    `_merge_yaml_string`), and iacs's merge already dedupes an exact repeat
    of an existing (owner, value) pair, so re-merging an already-known alias
    turn after turn is a harmless no-op rather than a growing pile of
    duplicate rows.
    """
    if not perceived_aliases:
        return
    data = {
        f"{owner_alias}_memory_update": [
            {"same_as": {"value": owner_alias}},
            {"memory": [{"value": alias} for alias in sorted(perceived_aliases)]},
        ]
    }
    _merge_yaml_string(registrar, WORLD_FILE_ID, yaml.safe_dump(data, sort_keys=False))


def _entity_descriptions(registrar: Registrar, aliases: set[str]) -> str:
    """Return one `alias: description` line per alias in `aliases` that has a `description`."""
    if not aliases:
        return ""
    df = _safe_view(registrar, "description.value")
    if df is None:
        return ""
    df = df[df["entity_id.alias"].isin(aliases)]
    return "\n".join(f"{row['entity_id.alias']}: {row['description.value']}" for _, row in df.iterrows())


def _ensure_player_alias(registrar: Registrar) -> str:
    """Return the player entity's alias, seeding a minimal one if none exists yet.

    On the very first turn there's no player entity for InputSystem/
    ResolverAgentSystem to attach an `input` component to, since the
    Archivist only creates one once it transcribes the first exchange. Seed
    a bare `player` entity (matching the alias archivist.yaml already
    instructs the Archivist to use) so `input` always has somewhere to live.
    """
    alias = _player_alias(registrar)
    if alias is not None:
        return alias
    data = {"player": [{"character": {"interaction_type": "player"}}]}
    _merge_yaml_string(registrar, WORLD_FILE_ID, yaml.safe_dump(data, sort_keys=False))
    return "player"


def _acting_character_alias(registrar: Registrar, turn: int) -> str | None:
    """Return the alias of whichever character produced a command ("player"-type input) this turn.

    Generalizes the old assumption that a turn's command always belongs to
    "the" player: it can now come from InputSystem (a human, always attached
    to the player entity) or NPCAgentSystem (an NPC, attached to that NPC's
    own entity). Used by ResolverAgentSystem to attach its reply onto the
    entity that actually acted this turn, instead of force-creating a player
    entity in an NPC-only world.
    """
    df = _safe_view(registrar, ["input.text", "input.type", "input.turn"])
    if df is None:
        return None
    matches = df[(df["input.type"] == "player") & (df["input.turn"] == turn)]
    if matches.empty:
        return None
    return matches.iloc[-1]["entity_id.alias"]


def _latest_input(registrar: Registrar, type_: str, turn: int) -> str | None:
    """Return the `type_`-authored input's text for `turn`, or None if not written yet.

    `input.turn` is schema-validated (type: int) by every ETL call that
    produces it, so `turn` is compared directly rather than coercing to
    string.
    """
    df = _safe_get(registrar, "input")
    if df is None:
        return None
    matches = df[(df["type"] == type_) & (df["turn"] == turn)]
    if matches.empty:
        return None
    return matches.iloc[-1]["text"]


def _active_aliases(registrar: Registrar) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    df = _safe_view(registrar, "active")
    if df is None:
        return set()
    return set(df["entity_id.alias"])


def _all_aliases(registrar: Registrar) -> set[str]:
    """Return the aliases of every positioned entity in the world.

    Deliberately narrower than every row in the `entity_id` table: `base_etl`
    always loads `MANIFEST_DIR` too, so the registry also carries builtin
    schema entities (component type definitions, audit templates, etc.) that
    have no place in the physical world and nothing useful to tell the
    Resolver. Restricting to entities with a `position` reuses the same
    "has a place in the world" criterion `_latest_positions` resolves for
    (including its own handling of `position` not being loaded yet), and
    excludes exactly the schema noise.
    """
    return set(_latest_positions(registrar)["entity_id.alias"])


def _build_prompt(actor_alias: str, text: str, active_aliases: set[str], entity_details: str = "") -> str:
    """Assemble a turn's prompt from the active entities, their details, and the actor's input.

    `entity_details` is folded in as its own out-of-character block, but only
    when non-empty, so a call without it (the common case in tests) still
    reduces to the same "Active entities nearby: .../{actor_alias}'s input:
    ..." shape this always had. Names the line by the acting character's own
    alias rather than a literal "Player input" — the actor isn't always the
    player (see NPCAgentSystem), and that literal wording was observed to
    make the Resolver narrate as if a separate "player" character were
    standing alongside whichever NPC was actually acting.
    """
    parts = []
    if active_aliases:
        parts.append(f"Active entities nearby: {', '.join(sorted(active_aliases))}")
    if entity_details:
        parts.append(f"Entity details:\n{entity_details}")
    if not parts:
        return text
    parts.append(f"{actor_alias}'s input: {text}")
    return "\n".join(parts)


def _build_npc_prompt(registrar: Registrar, alias: str) -> str:
    """Assemble an NPC's decision prompt from its agenda and what it has perceived.

    Deliberately narrower than `_build_prompt`'s `entity_details` (every
    known entity in the registry): an NPC only gets entities it has actually
    perceived — `active` (nearby right now) union `memory` (ever perceived;
    see MapSystem) — plus a description for each, so its decision is scoped
    to what it could plausibly know about.
    """
    agenda_df = _safe_view(registrar, "agenda.value")
    agenda_text = ""
    if agenda_df is not None:
        match = agenda_df[agenda_df["entity_id.alias"] == alias]
        if not match.empty:
            agenda_text = match.iloc[-1]["agenda.value"]

    active = _active_aliases(registrar) - {alias}
    memory = _memory_aliases(registrar, alias) - {alias}
    remembered_only = sorted(memory - active)
    details = _entity_descriptions(registrar, active | memory)

    parts = []
    if agenda_text:
        parts.append(f"Your agenda: {agenda_text}")
    if active:
        parts.append(f"Entities nearby right now: {', '.join(sorted(active))}")
    if remembered_only:
        parts.append(f"Entities you remember but can't currently perceive: {', '.join(remembered_only)}")
    if details:
        parts.append(f"What you know about them:\n{details}")
    parts.append(
        "What do you do this turn? Respond in first person, one or two "
        "sentences, exactly as if you were typing your action as a command."
    )
    return "\n".join(parts)
