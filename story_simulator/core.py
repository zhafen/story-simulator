"""The base event-driven simulation kernel: registry write/read primitives
and the event-loop boxes (pop/advance clock/predict/push) that don't
depend on any optional module.

Everything here has to work in a world with no character, NPC, physics
(specialist judgment), terrain, or spatial (position/distance/perception)
module active at all -- those are layered on top (see
`story_simulator.spatial`, `story_simulator.specialists`,
`mcp_server.advance_simulation`'s character branch), not baked in here.
Modules may depend on this and on each other, but nothing here may import
from an optional module -- that's what keeps "no modules enabled" a real,
runnable base rather than an unreachable configuration.
"""

from __future__ import annotations

__iacs__ = {
    "todo": (
        "The pop/is_event_valid/advance_clock/predict_event/push_event "
        "functions just live loose at module scope here. Evaluate whether "
        "the event loop deserves a more deliberate structure (a class, a "
        "dataclass-based state object, an explicit stage protocol) as more "
        "modules start hooking into it, instead of a flat function bag."
    )
}

import pandas as pd
import yaml
from iacs.registrar import Registrar

from story_simulator.config import MANIFEST_DIR, WORLD_FILE_ID


def merge_yaml_string(registrar: Registrar, yaml_text: str, time: float | None = None) -> None:
    """Run the ETL pipeline on a raw YAML string and merge the result into `registrar`.

    Same mechanism every write in this project uses (see the old
    `story_simulator.systems._merge_yaml_string`): `time`, when given, backfills
    whichever time_dimension field the merged data declares (world time,
    seconds since world creation) so `Registry.view_current` can resolve
    which of an entity's accumulated rows is current.
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
    *current* state rather than its full change history. A component type
    with no `time_dimension` field behaves exactly like `safe_view` (every
    row is "current").
    """
    names = [fields] if isinstance(fields, str) else fields
    tables = {name.split(".", 1)[0] for name in names}
    if not tables <= set(registrar.registry.component_types):
        return None
    try:
        return registrar.view_current(fields).execute()
    except KeyError:
        return None


# ---------------------------------------------------------------------------
# Event-driven simulation loop -- one function per box in the turn-anatomy
# diagram (see docs/architecture.md and the published turn-flow artifact).
# An individual-timestep event-driven simulation, but with the schedule
# itself living as registry data (a `next_due` component) rather than an
# in-memory priority queue -- see pop_event's docstring for why that's
# what makes resuming a paused turn safe (see story_simulator.resolve).
# ---------------------------------------------------------------------------


def due_by_entity(registrar: Registrar) -> pd.DataFrame:
    """One row per entity with a next_due of its own: `entity_id`, `due` (float).

    Casts explicitly to the manifest-declared `next_due.value: float` type:
    a save with zero `next_due` rows anywhere leaves the schema undeclared
    on a plain `Registrar.load()` reconnect (`declare_schema` only runs
    during the ETL/validation pipeline a real `update` merge goes through,
    not a bare reconnect), so `get` falls back to a generic `value: string`
    table and `.max()` over it can't be compared against a float fallback.
    """
    return (
        registrar.get("next_due")
        .group_by("entity_id")
        .aggregate(due=lambda t: t["value"].cast("float64").max())
        .execute()
    )


def pop_event(registrar: Registrar) -> str | None:
    """Pop event box: whichever entity, of any kind, is due soonest, or
    None if nothing is currently scheduled.

    No notion of "character" at all -- that's the character module's own
    concern (see `story_simulator.spatial.next_due_entity`, which layers
    "only characters, brand-new ones sort first" on top of this same
    `next_due` data). Here, an entity with no `next_due` row simply isn't
    a candidate (not sorted as due immediately): an entity only enters the
    schedule once something explicitly pushes it there (see `push_event`).
    An entity most recently pushed at `due_at=inf` is treated as
    permanently done, filtered out the same way -- see
    `mcp_server.resolve_event`.

    A plain read, not a destructive dequeue: `story_simulator.resolve`'s
    replay-from-the-top mechanism depends on this being safe to call again
    and again and get the same answer for the same registry state.
    """
    if "next_due" not in registrar.registry.component_types:
        return None
    due_df = registrar.view_current("next_due.value").execute()
    due_df = due_df[due_df["next_due.value"] < float("inf")]
    if due_df.empty:
        return None
    return due_df.sort_values("next_due.value").iloc[0]["entity_id.alias"]


def is_event_valid(registrar: Registrar, alias: str) -> bool:
    """Valid? box: is `alias` still a real, eligible entity.

    Always true today by construction -- `pop_event` always re-reads
    current state fresh rather than pre-computing events into a queue, so
    the classic "has this entity changed since it was scheduled" staleness
    problem this check exists for doesn't arise yet. This is the seam a
    future lookahead/precomputed-event design would extend: an event
    captured ahead of time would need to compare some snapshot taken when
    it was scheduled (e.g. a version or change count) against the current
    one to detect a stale entity before acting on it.
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
    due_df = due_by_entity(registrar)
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
    separate in-memory priority queue; `pop_event`'s live registry read
    *is* the queue. `time` should be given the same world-time stamp
    every other time_dimension'd write in this project uses (see
    `mcp_server._next_time_stamp`) -- `next_due.time` is time_dimension'd
    exactly like `position.time`/`state.time`, so an entity rescheduled
    more than once needs it to resolve which row is current.
    """
    data = {f"{alias}_next_due": [{"same_as": {"value": alias}}, {"next_due": {"value": due_at}}]}
    merge_yaml_string(registrar, yaml.safe_dump(data, sort_keys=False), time=time)
