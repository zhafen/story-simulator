"""Position/distance/perception primitives -- generic over any entity,
independent of whether it's a character.

Restored from `shelved/story_simulator/spatial.py` (see
docs/architecture.md and shelved/README.md for the shelving history) --
these geometry/generic-perception functions only, not the whole original
module. Character-specific behavior built on top of these (narrating to
a character, its memory, the character-event predicate `process_event`
uses) lives in `story_simulator.character` instead -- see that module's
own docstring for why the split. The old module's character-scheduling
functions (`next_due_entity`, `pop_event`, `select_character`, and the
`next_due`-based scheduler they supported) are deliberately NOT restored
at all: this design's own
character_aware_event_loop_reentry.entities_can_take_turns_via_the_event_model
requirement selected `character_turn_is_its_own_event_type` instead --
a character's turn is an ordinary `event` entity, scheduled by
`core.pop_event`'s existing soonest-end_time rule, not a second
character-priority scheduler layered on top.

Optional, layered on top of `story_simulator.core`'s base event loop --
a world with no position/distance/perception concept still runs the base
simulation fine.
"""

from __future__ import annotations

__iacs__ = {
    "solution of": (
        "character_aware_event_loop_reentry.available_context_depends_on_viewer"
        ".character_context_is_restricted.perceive"
    )
}

import math

import pandas as pd
import yaml
from emc2p.mcp_server import SOURCE_KEY
from emc2p.registrar import Registrar

from story_simulator import game_config


def latest_positions(registrar: Registrar) -> pd.DataFrame:
    """Return one row per entity: its highest-time `position` (resolves accumulated history)."""
    columns = ["entity_id", "entity_id.display_alias", "position.x", "position.y", "position.z", "position.time"]
    if "position" not in registrar.registry.component_types:
        return pd.DataFrame(columns=columns)
    return registrar.view_current(["position.x", "position.y", "position.z", "position.time"]).to_pandas()[columns]


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


def _perceptible_fov_tan() -> float:
    """tan of the angle below which an object blends into the background.

    An object subtending less than `game_config.PERCEPTIBLE_FOV_FRACTION`
    of a `game_config.FOV_DEGREES`-wide field of view blends into the
    background -- see `game_config`'s own docstring for the reasoning.
    """
    threshold_angle = math.radians(game_config.FOV_DEGREES * game_config.PERCEPTIBLE_FOV_FRACTION)
    return math.tan(threshold_angle)


def visibility_distance(size: float) -> float:
    """How far away an object of this characteristic size stays perceptible.

    See `_perceptible_fov_tan` for the geometry this is derived from.
    """
    return size / _perceptible_fov_tan()


def perceptible_entities(registrar: Registrar, center: "str | tuple[float, float]") -> set[str]:
    """Return the aliases of every positioned entity `center` can perceive.

    `center` is any positioned entity (or a bare point) -- no character
    concept here at all; `story_simulator.character.narrate_to_character`
    is what calls this specifically for a character.

    Each candidate's own visibility distance is computed from its `size`
    component (falling back to `game_config.DEFAULT_ENTITY_SIZE`) via the
    same geometry `visibility_distance` uses -- so a mountain stays
    visible from far further away than a dropped coin. A single
    relational query (join + filter) via ibis, not row iteration, so the
    comparison runs in the registry's own backend.
    """
    if "position" not in registrar.registry.component_types:
        return set()

    center_id = registrar.get_entity_id(center) if isinstance(center, str) else None
    cx, cy = _resolve_point(registrar, center)

    positions = registrar.view_current(["position.x", "position.y"]).to_table()
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

    return set(perceptible["entity_id.display_alias"].execute())


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
    registrar.update(yaml_strings={SOURCE_KEY: yaml.safe_dump(data, sort_keys=False)})


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
    desc_df = registrar.safe_view_current("description.value").to_pandas()
    if not desc_df.empty:
        for _, row in desc_df[desc_df["entity_id"].isin(entity_ids)].iterrows():
            parts_by_alias.setdefault(row["entity_id.display_alias"], []).append(str(row["description.value"]))
    state_df = registrar.safe_view_current("state.value").to_pandas()
    if not state_df.empty:
        for _, row in state_df[state_df["entity_id"].isin(entity_ids)].iterrows():
            parts_by_alias.setdefault(row["entity_id.display_alias"], []).append(f"(state: {row['state.value']})")

    return "\n".join(f"{alias}: {' '.join(parts)}" for alias, parts in sorted(parts_by_alias.items()))


def active_aliases(registrar: Registrar) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    df = registrar.safe_view("active").to_pandas()
    if df.empty:
        return set()
    return set(df["entity_id.display_alias"])
