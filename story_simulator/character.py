"""Everything dependent on being a character: the `character` component
itself, a character's memory, narrating to one, the character-event
predicate `process_event` uses, and an NPC's own decide step.

Split out from `story_simulator.spatial` (position/distance/perception,
generic over any entity) so that module stays genuinely
character-agnostic -- `perceptible_entities`/`entity_position`/etc. work
identically for a rock as for an NPC. Everything here, by contrast, only
means something because the entity in question is a character: whether
one is involved in an event at all, whether it's NPC- or human-voiced,
what it remembers, what it currently perceives (narrated specifically to
it), and what it decides to do next when nobody's telling it.
"""

from __future__ import annotations

__iacs__ = {
    "solution of": (
        "character_aware_event_loop_reentry.characters_cannot_modify_world_data_directly"
        ".decide_then_record_split"
    )
}

import yaml
from emc2p.mcp_server import SOURCE_KEY
from emc2p.registrar import Registrar

from story_simulator import spatial
from story_simulator.config import decide_responder
from story_simulator.resolve import JudgmentRequest, TurnReplay


def character_interaction_type(registrar: Registrar, alias: str) -> str | None:
    """Return `alias`'s `character.interaction_type` ("player"/"npc"), or None if unset."""
    entity_id = registrar.get_entity_id(alias)
    if entity_id is None:
        return None
    df = registrar.safe_view("character.interaction_type").to_pandas()
    if df.empty:
        return None
    match = df[df["entity_id"] == entity_id]
    return None if match.empty else str(match.iloc[0]["character.interaction_type"])


def character_in_event(registrar: Registrar, event_alias: str) -> str | None:
    """Return the alias of the character `event_alias`'s event involves, if any.

    An event can carry several involved_entity rows; this returns
    whichever one resolves to an entity with a `character` component
    (sorted, for a deterministic answer if more than one somehow does).
    None for an ordinary base-module event -- no involved_entity at all,
    or none of its involved entities is a character.
    """
    if "involved_entity" not in registrar.registry.component_types:
        return None
    if "character" not in registrar.registry.component_types:
        return None
    entity_id = registrar.get_entity_id(event_alias)
    if entity_id is None:
        return None
    involved = registrar.view_current(["involved_entity.value"]).to_pandas()
    linked_aliases = set(involved[involved["entity_id"] == entity_id]["involved_entity.value"])
    if not linked_aliases:
        return None
    characters = set(registrar.view_current(["character.interaction_type"]).to_pandas()["entity_id.alias"])
    matches = linked_aliases & characters
    return min(matches) if matches else None


def is_character_event(registrar: Registrar, event_alias: str) -> bool:
    """True if `event_alias`'s event involves a character -- this event
    IS that character's own turn, not an ordinary base-module event."""
    return character_in_event(registrar, event_alias) is not None


def memory_aliases(registrar: Registrar, owner_alias: str) -> set[str]:
    """Return every alias `owner_alias` has ever perceived (see `record_memory`)."""
    df = registrar.safe_view("memory.value").to_pandas()
    if df.empty:
        return set()
    owner_id = registrar.get_entity_id(owner_alias)
    if owner_id is None:
        return set()
    return set(df[df["entity_id"] == owner_id]["memory.value"])


def record_memory(registrar: Registrar, owner_alias: str, perceived_aliases: set[str]) -> None:
    """Merge `perceived_aliases` into `owner_alias`'s permanent `memory` relation.

    Unlike `active`, `memory` is never cleared -- a character's memory only
    grows. Re-merging an already-known alias is a harmless no-op (emc2p's
    own Registry.merge dedupes exact repeats), so this is safe to call
    every time `narrate_to_character` runs.
    """
    if not perceived_aliases:
        return
    data = {
        f"{owner_alias}_memory_update": [
            {"same_as": {"value": owner_alias}},
            {"memory": [{"value": alias} for alias in sorted(perceived_aliases)]},
        ]
    }
    registrar.update(yaml_strings={SOURCE_KEY: yaml.safe_dump(data, sort_keys=False)})


def narrate_to_character(registrar: Registrar, alias: str) -> str:
    """What `alias` can currently perceive, and record it.

    Tags each perceived entity `active` (replacing whatever was previously
    tagged active, via `spatial.sync_active_tags`) and merges them into
    `alias`'s permanent `memory`. The bounded content `decide_event`
    builds its prompt from -- see
    character_aware_event_loop_reentry's own character_context_is_restricted
    requirement for why this exists as a real computed restriction rather
    than a prompt instruction alone.
    """
    nearby = spatial.perceptible_entities(registrar, alias)
    spatial.sync_active_tags(registrar, nearby)
    record_memory(registrar, alias, nearby)
    if not nearby:
        return f"Nothing else is within perceptible range of {alias}."
    details = spatial.entity_descriptions(registrar, nearby)
    parts = [f"Entities near {alias}: {', '.join(sorted(nearby))}"]
    if details:
        parts.append(details)
    return "\n".join(parts)


async def decide_event(registrar: Registrar, alias: str, replay: TurnReplay, session) -> str:
    """Decide box: ask what `alias` (an NPC) does next, restricted to
    only what it would currently perceive -- no update_registry access,
    unlike every other call in `core`'s event loop. `core.resolve_event`,
    next, is the one with real write authority to record the
    consequences.

    Only reached for an NPC-controlled character (see
    `core.process_event`'s own branch) -- a human-voiced character's own
    stated action is normally already known to the host from the ongoing
    conversation, so there's nothing to autonomously decide for one of
    those. `core.resolve_event`'s own `human_character_alias` handling is
    what covers the case where that assumption doesn't actually hold.

    The perceived-entities text embedded in the prompt (via
    `narrate_to_character`) is what makes this a real, computed content
    restriction rather than a bare instruction to imagine one -- see
    character_aware_event_loop_reentry's own
    character_context_is_restricted requirement. Nothing here stops the
    responder from calling other tools anyway (see the con already
    recorded on this requirement's decide_then_record_split solution);
    only the *given* content is scoped, not enforced access.
    """
    perceived = narrate_to_character(registrar, alias)
    request = JudgmentRequest(
        prompt=(
            f"{alias} is deciding what to do next. Base this only on "
            f"what {alias} can currently perceive, given below -- do "
            f"not use any other information about the world:\n\n"
            f"{perceived}\n\n"
            f"Describe {alias}'s action in plain text. Do NOT call "
            f"update_registry here -- this step only decides; a "
            f"separate step (resolve_event, next) has the real write "
            f"authority to record it."
        ),
        origin="decide_event",
    )
    return await replay.resolve(request, responder=decide_responder(), session=session)
