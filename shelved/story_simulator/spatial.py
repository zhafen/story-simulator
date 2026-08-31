"""Position/distance/perception helpers shared by the MCP server's tools.

Optional, layered on top of `story_simulator.core`'s base event loop --
a world with no position/distance/perception concept still runs the base
simulation fine. Plain functions any tool can call on demand, not an
automatic per-turn pass: `perceive` (mcp_server.py) calls these for
whichever character it names, since there's no single privileged "the
player" anymore -- every function here takes its reference character
explicitly.
"""

from __future__ import annotations

__iacs__ = {"solution of": "story_simulator_mission.tool_catalog.perceive"}

import math

import pandas as pd
import yaml
from emc2p.registrar import Registrar

from story_simulator import game_config
from story_simulator.core import due_by_entity, merge_yaml_string


def latest_positions(registrar: Registrar) -> pd.DataFrame:
    """Return one row per entity: its highest-time `position` (resolves accumulated history)."""
    columns = ["entity_id", "entity_id.alias", "position.x", "position.y", "position.z", "position.time"]
    if "position" not in registrar.registry.component_types:
        return pd.DataFrame(columns=columns)
    return registrar.view_current(["position.x", "position.y", "position.z", "position.time"]).execute()[columns]


def entity_position(registrar: Registrar, alias: str) -> tuple[float, float] | None:
    """Return the (x, y) position of the entity aliased `alias`, or None if it has none yet.

    Resolves `alias` via `Registrar.get_entity_id` (exact hash, else exact
    alias, else unambiguous path fragment), the same way `same_as`/
    `entity_ref` fields already resolve one.
    """
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return None
    positions = latest_positions(registrar)
    match = positions[positions["entity_id"] == entity_id]
    if match.empty:
        return None
    row = match.iloc[0]
    return (float(row["position.x"]), float(row["position.y"]))


def _resolve_point(registrar: Registrar, value: "str | tuple[float, float]") -> tuple[float, float]:
    """Resolve `value` to an (x, y) point, looking it up as an entity alias if it's a string."""
    if not isinstance(value, str):
        return value
    pos = entity_position(registrar, value)
    if pos is None:
        raise ValueError(f"No known position for entity alias {value!r}")
    return pos


def distance(registrar: Registrar, a: "str | tuple[float, float]", b: "str | tuple[float, float]") -> float:
    """Euclidean distance between `a` and `b`, each an entity alias or a bare (x, y) point."""
    return math.dist(_resolve_point(registrar, a), _resolve_point(registrar, b))


def entities_within(registrar: Registrar, center: "str | tuple[float, float]", radius: float) -> set[str]:
    """Return the aliases of every positioned entity within `radius` of `center`.

    `center` is an entity alias or a bare (x, y) point; when it's an
    alias, that entity itself is excluded from the result.
    """
    center_id = registrar.get_entity_id(center) if isinstance(center, str) else None
    center_pos = _resolve_point(registrar, center)
    positions = latest_positions(registrar)
    result = set()
    for _, row in positions.iterrows():
        if center_id is not None and row["entity_id"] == center_id:
            continue
        pos = (float(row["position.x"]), float(row["position.y"]))
        if math.dist(pos, center_pos) <= radius:
            result.add(row["entity_id.alias"])
    return result


def _perceptible_fov_tan() -> float:
    """tan of the angle below which an object blends into the background.

    An object subtending less than `game_config.PERCEPTIBLE_FOV_FRACTION`
    of a `game_config.FOV_DEGREES`-wide field of view blends into the
    background -- see `game_config`'s own docstring for the reasoning.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.perceive"}
    threshold_angle = math.radians(game_config.FOV_DEGREES * game_config.PERCEPTIBLE_FOV_FRACTION)
    return math.tan(threshold_angle)


def visibility_distance(size: float) -> float:
    """How far away an object of this characteristic size stays perceptible.

    See `_perceptible_fov_tan` for the geometry this is derived from.
    """
    return size / _perceptible_fov_tan()


def perceptible_entities(registrar: Registrar, center: "str | tuple[float, float]") -> set[str]:
    """Return the aliases of every positioned entity `center` can perceive.

    Unlike `entities_within`'s single flat cutoff, each candidate's own
    visibility distance is computed from its `size` component (falling
    back to `game_config.DEFAULT_ENTITY_SIZE`) via the same geometry
    `visibility_distance` uses -- so a mountain stays visible from far
    further away than a dropped coin. A single relational query (join +
    filter) via ibis, not row iteration, so the comparison runs in the
    registry's own backend.
    """
    if "position" not in registrar.registry.component_types:
        return set()

    center_id = registrar.get_entity_id(center) if isinstance(center, str) else None
    cx, cy = _resolve_point(registrar, center)

    positions = registrar.view_current(["position.x", "position.y"])
    # Cast to `size.value: float` explicitly: when no entity anywhere in
    # the save has ever had a `size` component, reopening it leaves that
    # schema undeclared, so `get` falls back to a string table that can't
    # coalesce with the float `DEFAULT_ENTITY_SIZE` fallback below.
    sizes = (
        registrar.get("size")
        .group_by("entity_id")
        .aggregate(size=lambda t: t["value"].cast("float64").max())
    )
    joined = positions.left_join(sizes, positions["entity_id"] == sizes["entity_id"])

    size_col = joined["size"].fill_null(game_config.DEFAULT_ENTITY_SIZE)
    distance_expr = ((joined["position.x"] - cx) ** 2 + (joined["position.y"] - cy) ** 2).sqrt()
    visible_radius = size_col / _perceptible_fov_tan()

    perceptible = joined.filter(distance_expr <= visible_radius)
    if center_id is not None:
        perceptible = perceptible.filter(perceptible["entity_id"] != center_id)

    return set(perceptible["entity_id.alias"].execute())


def sync_active_tags(registrar: Registrar, active_aliases: set[str]) -> None:
    """Overwrite the `active` component table so it exactly matches `active_aliases`.

    A merge can only union rows in, never drop a tag, so the existing
    `active` table is cleared first, then the current set is merged back in
    via `same_as` so each tag attaches to its alias's existing entity.
    """
    if "active" in registrar.registry.component_types:
        registrar.overwrite("active", registrar.get("active").limit(0).to_pyarrow())
    if not active_aliases:
        return
    data = {
        f"{alias}_update": [{"same_as": {"value": alias}}, "active"] for alias in sorted(active_aliases)
    }
    merge_yaml_string(registrar, yaml.safe_dump(data, sort_keys=False))


def memory_aliases(registrar: Registrar, owner_alias: str) -> set[str]:
    """Return every alias `owner_alias` has ever perceived (see `record_memory`)."""
    df = registrar.safe_view("memory.value")
    if df is None:
        return set()
    owner_id = registrar.get_entity_id(owner_alias)
    if owner_id is None:
        return set()
    return set(df[df["entity_id"] == owner_id]["memory.value"])


def record_memory(registrar: Registrar, owner_alias: str, perceived_aliases: set[str]) -> None:
    """Merge `perceived_aliases` into `owner_alias`'s permanent `memory` relation.

    Unlike `active`, `memory` is never cleared — a character's memory only
    grows. Re-merging an already-known alias is a harmless no-op (emc2p's
    own Registry.merge dedupes exact repeats), so this is safe to call
    every time `perceive` runs.
    """
    if not perceived_aliases:
        return
    data = {
        f"{owner_alias}_memory_update": [
            {"same_as": {"value": owner_alias}},
            {"memory": [{"value": alias} for alias in sorted(perceived_aliases)]},
        ]
    }
    merge_yaml_string(registrar, yaml.safe_dump(data, sort_keys=False))


def entity_descriptions(registrar: Registrar, aliases: set[str]) -> str:
    """Return one `alias: description (state: ...)` line per alias with a `description` or `state`.

    Reads via `safe_view_current`, not `safe_view`: both fields are
    time_dimension'd, so this shows an entity's current description/state,
    not every historical restatement of it.
    """
    if not aliases:
        return ""
    entity_ids = {
        entity_id for alias in aliases if (entity_id := registrar.get_entity_id(alias)) is not None
    }
    if not entity_ids:
        return ""

    parts_by_alias: dict[str, list[str]] = {}
    desc_df = registrar.safe_view_current("description.value")
    if desc_df is not None:
        for _, row in desc_df[desc_df["entity_id"].isin(entity_ids)].iterrows():
            parts_by_alias.setdefault(row["entity_id.alias"], []).append(str(row["description.value"]))
    state_df = registrar.safe_view_current("state.value")
    if state_df is not None:
        for _, row in state_df[state_df["entity_id"].isin(entity_ids)].iterrows():
            parts_by_alias.setdefault(row["entity_id.alias"], []).append(f"(state: {row['state.value']})")

    return "\n".join(f"{alias}: {' '.join(parts)}" for alias, parts in sorted(parts_by_alias.items()))


def active_aliases(registrar: Registrar) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    df = registrar.safe_view("active")
    if df is None:
        return set()
    return set(df["entity_id.alias"])


def character_interaction_type(registrar: Registrar, alias: str) -> str | None:
    """Return `alias`'s `character.interaction_type` ("player"/"npc"), or None if unset.

    Used to branch between the player-voiced path (responder="human") and
    the NPC path (responder="keyed_subagent").
    """
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return None
    df = registrar.safe_view("character.interaction_type")
    if df is None:
        return None
    match = df[df["entity_id"] == entity_id]
    return None if match.empty else str(match.iloc[0]["character.interaction_type"])


# ---------------------------------------------------------------------------
# The character module's own scheduling: layers "only characters, and a
# brand-new one sorts first" on top of core.py's plain next_due data.
# ---------------------------------------------------------------------------


def next_due_entity(registrar: Registrar) -> str | None:
    """Return the alias of whichever character is due soonest, or None if there are none.

    A character with no `next_due` row yet sorts as due immediately
    (-inf), so a brand-new character always goes before anything already
    scheduled -- overriding `core.pop_event`'s base rule (nothing is a
    candidate without an explicit `next_due` row) for characters
    specifically. A plain read, not a destructive dequeue:
    `story_simulator.resolve`'s replay-from-the-top mechanism depends on
    calling this again and again being safe.
    """
    if "character" not in registrar.registry.component_types:
        return None
    characters = registrar.view_current(["character.interaction_type"]).execute()
    if characters.empty:
        return None
    due_df = due_by_entity(registrar)
    merged = characters.merge(due_df, on="entity_id", how="left")
    merged["due"] = merged["due"].fillna(float("-inf"))
    return merged.sort_values("due").iloc[0]["entity_id.alias"]


def pop_event(registrar: Registrar) -> str | None:
    """Pop event box: identify (not destructively dequeue) whichever character is due next."""
    return next_due_entity(registrar)


def select_character(registrar: Registrar, alias: str) -> str:
    """Select character box: resolve/validate the alias `process_event` was already handed.

    Not a "pick among many" step -- `pop_event` already chose which entity
    is due. This just confirms `alias` still resolves to a real entity.
    """
    if registrar.get_entity_id(alias) is None:
        raise ValueError(f"No such character: {alias!r}")
    return alias


def narrate_to_character(registrar: Registrar, alias: str) -> str:
    """Narrate to character box: what `alias` can currently perceive, and record it.

    Tags each perceived entity `active` (replacing whatever was previously
    tagged active) and merges them into `alias`'s permanent `memory`. This
    is the `perceive` tool's own body, factored out here so
    `character_communication` (mcp_server.py) can call it directly instead
    of going through a second MCP round-trip.
    """
    nearby = perceptible_entities(registrar, alias)
    sync_active_tags(registrar, nearby)
    record_memory(registrar, alias, nearby)
    if not nearby:
        return f"Nothing else is within perceptible range of {alias}."
    details = entity_descriptions(registrar, nearby)
    parts = [f"Entities near {alias}: {', '.join(sorted(nearby))}"]
    if details:
        parts.append(details)
    return "\n".join(parts)
