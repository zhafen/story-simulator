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

import pandas as pd
import yaml
from iacs.registrar import Registrar

from story_simulator import game_config
from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID


def merge_yaml_string(registrar: Registrar, yaml_text: str, time: float | None = None) -> None:
    """Run the ETL pipeline on a raw YAML string and merge the result into `registrar`.

    Same mechanism every write in this project uses (see the old
    `story_simulator.systems._merge_yaml_string`): `time`, when given, backfills
    the `position.time` time-dimension field (world time, seconds since world
    creation) so `latest_positions` can resolve which of an entity's
    accumulated position rows is current.
    """
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text}, time=time)


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


def safe_view_current(registrar: Registrar, fields: str | list[str]) -> pd.DataFrame | None:
    """Like `safe_view`, but resolves each field's current row per entity.

    Uses `registrar.view_current` (see `Registry.view_current`) instead of
    `view` -- the right choice for anything meant to show an entity's
    *current* state (`perceive`, narration) rather than its full change
    history. A component type with no `time_dimension` field behaves
    exactly like `safe_view` (every row is "current").
    """
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view_current(fields).execute()
    except KeyError:
        return None


def latest_positions(registrar: Registrar) -> pd.DataFrame:
    """Return one row per entity: its highest-time `position` (resolves accumulated history)."""
    columns = ["entity_id", "entity_id.alias", "position.x", "position.y", "position.z", "position.time"]
    if "position" not in registrar.registry.component_types:
        return pd.DataFrame(columns=columns)
    return registrar.view_current(["position.x", "position.y", "position.z", "position.time"]).execute()[columns]


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
    # Cast to the manifest-declared `size.value: float` type explicitly rather than
    # trusting whatever dtype `registrar.get` infers: when no entity anywhere in the
    # save has ever had a `size` component, reopening the save (a plain DB reconnect,
    # not a manifest re-merge) leaves that schema undeclared, so `get` falls back to
    # a generic `value: string` empty table -- and `.max()` over a string column
    # produces a string `size` column that then fails to coalesce with the float
    # `DEFAULT_ENTITY_SIZE` fallback below.
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
    """Return one `alias: description (state: ...)` line per alias with a `description` or `state`.

    Reads via `safe_view_current`, not `safe_view`: both `description` and
    `state` are time_dimension'd (see manifest/builtins.yaml and iacs's own
    `description` component), so this shows an entity's current description/
    state -- not every historical restatement of it.
    """
    if not aliases:
        return ""
    entity_ids = {
        entity_id for alias in aliases if (entity_id := registrar.get_entity_id(alias)) is not None
    }
    if not entity_ids:
        return ""

    parts_by_alias: dict[str, list[str]] = {}
    desc_df = safe_view_current(registrar, "description.value")
    if desc_df is not None:
        for _, row in desc_df[desc_df["entity_id"].isin(entity_ids)].iterrows():
            parts_by_alias.setdefault(row["entity_id.alias"], []).append(str(row["description.value"]))
    state_df = safe_view_current(registrar, "state.value")
    if state_df is not None:
        for _, row in state_df[state_df["entity_id"].isin(entity_ids)].iterrows():
            parts_by_alias.setdefault(row["entity_id.alias"], []).append(f"(state: {row['state.value']})")

    return "\n".join(f"{alias}: {' '.join(parts)}" for alias, parts in sorted(parts_by_alias.items()))


def active_aliases(registrar: Registrar) -> set[str]:
    """Return the aliases of every entity currently tagged `active`."""
    df = safe_view(registrar, "active")
    if df is None:
        return set()
    return set(df["entity_id.alias"])


def character_interaction_type(registrar: Registrar, alias: str) -> str | None:
    """Return `alias`'s `character.interaction_type` ("player"/"npc"), or None if unset.

    Used by `get_character_input`/`resolve_event` (mcp_server.py) to branch
    between the player-voiced path (responder="human" -- only a real human
    can answer) and the NPC path (responder="subagent" -- nobody real is
    behind it).
    """
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return None
    df = safe_view(registrar, "character.interaction_type")
    if df is None:
        return None
    match = df[df["entity_id"] == entity_id]
    return None if match.empty else str(match.iloc[0]["character.interaction_type"])


# ---------------------------------------------------------------------------
# Event-driven simulation loop -- one function per box in the turn-anatomy
# diagram (see docs/architecture.md and the published turn-flow artifact).
# Modeled on Sedgewick & Wayne's individual-timestep event-driven
# simulation, but with the schedule itself living as registry data (a
# `next_due` component) rather than an in-memory priority queue -- see
# next_due_entity's docstring for why that's what makes resuming a paused
# turn safe (see story_simulator.resolve).
# ---------------------------------------------------------------------------


def _next_due_by_entity(registrar: Registrar) -> pd.DataFrame:
    """One row per entity with a next_due of its own: `entity_id`, `due` (float).

    Casts explicitly to the manifest-declared `next_due.value: float` type,
    for the same reason `perceptible_entities` casts `size`: a save with
    zero `next_due` rows anywhere leaves the schema undeclared on a plain
    `Registrar.load()` reconnect (`declare_schema` only runs during the
    ETL/validation pipeline a real `update` merge goes through, not a bare
    reconnect), so `get` falls back to a generic `value: string` table and
    `.max()` over it can't be compared against a float fallback.
    """
    return (
        registrar.get("next_due")
        .group_by("entity_id")
        .aggregate(due=lambda t: t["value"].cast("float64").max())
        .execute()
    )


def next_due_entity(registrar: Registrar) -> str | None:
    """Return the alias of whichever character is due soonest, or None if there are none.

    A character with no `next_due` row yet sorts as due immediately
    (-inf), so a brand-new character always goes before anything already
    scheduled into the future. Only characters are scheduled -- non-character
    entities (objects, terrain) don't take turns. A plain read, not a
    destructive dequeue: `story_simulator.resolve`'s replay-from-the-top
    mechanism depends on this being safe to call again and again and get
    the same answer for the same registry state.
    """
    if "character" not in registrar.registry.component_types:
        return None
    characters = registrar.view_current(["character.interaction_type"]).execute()
    if characters.empty:
        return None
    due_df = _next_due_by_entity(registrar)
    merged = characters.merge(due_df, on="entity_id", how="left")
    merged["due"] = merged["due"].fillna(float("-inf"))
    return merged.sort_values("due").iloc[0]["entity_id.alias"]


def pop_event(registrar: Registrar) -> str | None:
    """Pop event box: identify (not destructively dequeue) whichever character is due next."""
    return next_due_entity(registrar)


def is_event_valid(registrar: Registrar, alias: str) -> bool:
    """Valid? box: is `alias` still a real, eligible character.

    Always true today by construction -- `pop_event` always re-reads
    current state fresh rather than pre-computing events into a queue, so
    the classic "has this entity changed since it was scheduled" staleness
    problem (Sedgewick & Wayne's own reason for this check) doesn't arise
    yet. This is the seam a future lookahead/precomputed-event design
    would extend, the same way `CollisionSystem.Event.isValid()` compares
    a captured collision count against the current one.
    """
    return registrar.get_entity_id(alias) is not None


def advance_clock(registrar: Registrar, alias: str) -> float:
    """Advance clock box: the popped entity's own `next_due` becomes "now" for this turn.

    No separate persisted global clock yet -- the popped event's own
    timestamp is the only notion of "current time" anything downstream
    needs today. A shared clock entity would only become necessary if
    something other than "whichever event was just popped" ever needed to
    read "now" independently.
    """
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return 0.0
    due_df = _next_due_by_entity(registrar)
    match = due_df[due_df["entity_id"] == entity_id]
    return float(match.iloc[0]["due"]) if not match.empty else 0.0


def predict_event(registrar: Registrar, alias: str, next_due_in: float) -> float:
    """Predict events / Predict next box: compute when `alias` should next be due.

    One function serving both call sites, per the diagram's own "same
    function as" edge -- the initial per-entity setup and the
    post-`Process event` reschedule are the identical computation, just
    invoked for a different set of entities at different points in the
    loop. Pure: doesn't write anything itself (see `push_event`).
    """
    now = advance_clock(registrar, alias)
    return now + next_due_in


def push_event(registrar: Registrar, alias: str, due_at: float, time: float | None = None) -> None:
    """Push to queue / Push events box: commit `alias`'s next_due to the registry.

    One function serving both call sites, matching `predict_event`.
    Writing `next_due` IS "pushing to the queue" here -- there's no
    separate in-memory priority queue; `next_due_entity`'s live registry
    read *is* the queue. `time` should be given the same world-time stamp
    every other time_dimension'd write in this project uses (see
    `mcp_server._next_time_stamp`) -- `next_due.time` is time_dimension'd
    exactly like `position.time`/`state.time`, so an entity rescheduled
    more than once needs it to resolve which row is current.
    """
    data = {f"{alias}_next_due": [{"same_as": {"value": alias}}, {"next_due": {"value": due_at}}]}
    merge_yaml_string(registrar, yaml.safe_dump(data, sort_keys=False), time=time)


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
    tagged active) and merges them into `alias`'s permanent `memory`, the
    same way the old per-turn MapSystem did -- just on demand instead of
    automatically every turn. This is the `perceive` tool's own body,
    factored out here so `character_communication` (mcp_server.py) can
    call it directly instead of going through a second MCP round-trip.
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
