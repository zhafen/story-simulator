"""Position/distance/perception helpers shared by the MCP server's tools.

Ported from the old per-turn `MapSystem` into plain functions any tool can
call on demand: there's no more automatic per-turn pass recomputing "what's
active" for a fixed reference character, since there's no more per-turn
pipeline at all. `perceive` (in `mcp_server.py`) calls these when a caller
actually asks who/what a given character can perceive, for whichever
character it names — there's no single privileged "the player" anymore, so
every function here takes its reference character explicitly.
"""

from __future__ import annotations

__iacs__ = {"solution of": "story_simulator_mission.tool_catalog.perceive"}

import math

import ibis
import pandas as pd
import yaml
from iacs.registrar import Registrar

from story_simulator import game_config
from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID


def merge_yaml_string(registrar: Registrar, yaml_text: str, turn: int | None = None) -> None:
    """Run the ETL pipeline on a raw YAML string and merge the result into `registrar`.

    Same mechanism every write in this project uses (see the old
    `story_simulator.systems._merge_yaml_string`): `turn`, when given, backfills
    the `position.turn` time-dimension field so `latest_positions` can resolve
    which of an entity's accumulated position rows is current.
    """
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text}, time=turn)


def safe_view(registrar: Registrar, fields: str | list[str]) -> pd.DataFrame | None:
    """Execute `registrar.view(fields)`, or None if that component type isn't loaded yet."""
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view(fields).execute()
    except KeyError:
        return None


def latest_positions(registrar: Registrar) -> pd.DataFrame:
    """Return one row per entity: its highest-turn `position` (resolves accumulated history)."""
    columns = ["entity_id", "entity_id.alias", "position.x", "position.y", "position.z", "position.turn"]
    if "position" not in registrar.registry.component_types:
        return pd.DataFrame(columns=columns)
    return registrar.view_current(["position.x", "position.y", "position.z", "position.turn"]).execute()[columns]


def entity_position(registrar: Registrar, alias: str) -> tuple[float, float] | None:
    """Return the (x, y) position of the entity aliased `alias`, or None if it has none yet.

    Resolves `alias` via `Registrar.get_entity_id` (exact hash, else exact
    alias, else unambiguous path fragment) rather than a literal
    `entity_id.alias ==` string match, so a dotted path fragment (e.g.
    "desk" for "journaling_desk.desk") or a raw entity_id hash resolves the
    same way `same_as`/`entity_ref` fields already do.
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

    `center` is an entity alias or a bare (x, y) point; when it's an alias,
    that entity itself is excluded from the result (resolved via
    `Registrar.get_entity_id`, so a path fragment or raw hash excludes the
    right entity even when it doesn't match `entity_id.alias` literally).
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

    An object subtending less than `game_config.PERCEPTIBLE_FOV_FRACTION` of
    a `game_config.FOV_DEGREES`-wide field of view blends into the
    background rather than staying perceptible -- see
    `data/living_world/scenario.yaml`'s journaling_desk placement note and
    `game_config`'s own docstring for the reasoning and the real-world
    figures it was checked against.
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

    Unlike `entities_within`'s single flat cutoff for every entity, each
    candidate's own visibility distance is computed from its `size`
    component (falling back to `game_config.DEFAULT_ENTITY_SIZE` when it has
    none) via the same geometry `visibility_distance` uses -- so a mountain
    stays visible from far further away than a dropped coin, with no extra
    calculation required of the caller beyond making sure entities carry a
    `size` component. Done as a single relational query (join + filter) via
    ibis rather than iterating rows in Python, so the comparison runs in the
    registry's own backend.
    """
    if "position" not in registrar.registry.component_types:
        return set()

    center_id = registrar.get_entity_id(center) if isinstance(center, str) else None
    cx, cy = _resolve_point(registrar, center)

    positions = registrar.view_current(["position.x", "position.y"])

    # "size" may not be a known component type at all yet -- a fresh
    # Registrar.load() only recovers declared schemas from tables that
    # already have data (see Registry.get), so if no entity anywhere has
    # ever carried a `size` component, registrar.get("size") falls back to
    # a generic entity_id/value-as-string schema, and fill_null(<float>)
    # against that string column blows up with a string/float64 precedence
    # error instead of a sensible default. Skip the join entirely in that
    # case and treat every candidate as game_config.DEFAULT_ENTITY_SIZE.
    if "size" in registrar.registry.component_types:
        sizes = registrar.get("size").group_by("entity_id").aggregate(size=lambda t: t["value"].max())
        joined = positions.left_join(sizes, positions["entity_id"] == sizes["entity_id"])
        size_col = joined["size"].fill_null(game_config.DEFAULT_ENTITY_SIZE)
    else:
        joined = positions
        size_col = ibis.literal(game_config.DEFAULT_ENTITY_SIZE)

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
    df = safe_view(registrar, "memory.value")
    if df is None:
        return set()
    owner_id = registrar.get_entity_id(owner_alias)
    if owner_id is None:
        return set()
    return set(df[df["entity_id"] == owner_id]["memory.value"])


def record_memory(registrar: Registrar, owner_alias: str, perceived_aliases: set[str]) -> None:
    """Merge `perceived_aliases` into `owner_alias`'s permanent `memory` relation.

    Unlike `active`, `memory` is never cleared — a character's memory only
    grows. Re-merging an already-known alias is a harmless no-op (iacs
    dedupes exact repeats), so this is safe to call every time `perceive` runs.
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
    """Return one `alias: description` line per alias in `aliases` that has a `description`."""
    if not aliases:
        return ""
    df = safe_view(registrar, "description.value")
    if df is None:
        return ""
    entity_ids = {
        entity_id for alias in aliases if (entity_id := registrar.get_entity_id(alias)) is not None
    }
    df = df[df["entity_id"].isin(entity_ids)]
    return "\n".join(f"{row['entity_id.alias']}: {row['description.value']}" for _, row in df.iterrows())


def active_aliases(registrar: Registrar) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    df = safe_view(registrar, "active")
    if df is None:
        return set()
    return set(df["entity_id.alias"])
