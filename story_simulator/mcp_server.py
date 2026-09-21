"""MCP server exposing story-simulator's world-state and event-loop tools.

story-simulator is *just* this server today -- no in-process agent loop
lives here. `advance_simulation` runs ONE event-driven simulation loop (one
function per step -- see `core._run_event_loop`), built entirely on
`story_simulator.core`'s `pop_event`/`resolve_event`/`plan_events` -- see
`core.py`'s own docstring for what that guarantees. World state is `event`
entities (manifest/builtins.yaml's event_components), each ready to
resolve once world time reaches its own end_time (start_time +
duration) -- not the acting entities (a car, a door, ...) themselves,
which carry no schedule of their own. The
loop fast-forwards through anything it can resolve on its own, and pauses
whenever a turn needs input only the connected host can supply -- an
event's own resolution, or what (if anything) follows from it -- handing
control back to whatever MCP-aware host is connected (a human's chat
agent, an automated harness, ...). That host decides what happens itself
(`responder="host"`, the default) or is asked to delegate to its own
isolated subagent mechanism instead (`responder="subagent"`, opt in via
STORY_SIM_RESPONDER -- see `story_simulator.config.event_responder`) -- see
`advance_simulation`'s own `responder` field -- then calls
`advance_simulation` again with its decision (recorded via
`update_registry`) and the `resume_token` it was given, to resume the loop
-- Multi Round-Trip Requests (MRTR, MCP spec 2026-07-28), not a second
dedicated tool. `view_registry`/`view_entity`/`update_registry` remain
directly callable too, for anything outside that loop.

`view_registry`/`view_entity`/`update_registry`/`consolidate_review` are
`core.registrar_sessions`'s own tools (a `RegistrarSessions` instance from
`emc2p.mcp_server` -- see that class's own docstring), mounted directly
onto this server (see the `.mount()` call near the bottom of this file)
rather than reimplemented or manually delegated to here -- registry
read/write is emc2p's job, generalized, not story-simulator's own to
duplicate. `open_registry` (emc2p's own tool for opening a registrar by
database_url) is excluded from the mount: this server already has
`start_world` for that (Postgres bootstrap, save_dir seeding/export
wiring included), and mounting `open_registry` too would let a client
silently swap out the world's own registrar for an unrelated one
mid-session.

This file is deliberately thin: every `@server.tool()` function below just
unpacks `ctx.request_context.session` into a plain session id and calls
straight into `story_simulator.core`, which owns the actual implementation
(including session state, Postgres bootstrap, world save I/O, and the event
loop itself). Each tool's own `description` is passed explicitly as
`core.<name>.__doc__` -- the wrapper function below has no docstring of
its own to keep in sync -- so what a connected host reads is `core.py`'s
docstring verbatim, not a second, separately-maintained restatement of
it. Same pattern `core.registrar_sessions.mount()` (below) already uses
for its own four tools.

The event loop's character-aware branch (an NPC's own decide step,
`character.decide_event`) is live -- see `advance_simulation`'s own docstring.
`perceive`/`advance_npc_turn`/`generate_terrain`/`resolve_physics` as
standalone, directly callable tools are still shelved (see
`docs/architecture.md`): perception and an NPC's turn are handled inside
the event loop itself now, not forced out-of-band -- not deleted, and
easy to pull back in piece by piece if that turns out to be wrong.

The judgment resolver behind all of this (`story_simulator.resolve`) is
what lets `core.resolve_event` reach a real decision from any nesting depth
without every intervening function having to be a generator -- see that
module's docstring.

Structurally mirrors `iacs/iacs/mcp_server.py`: plain `@server.tool()`
functions, `server.run(transport="stdio")`.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import Context, FastMCP

from story_simulator import core

server = FastMCP(
    "story-simulator",
    instructions=(
        "You are the game master for a story-simulator world: a text simulation whose "
        "state lives in a structured entity/component registry, not just your own context, "
        "run as an event-driven simulation. World state is `event` entities -- each ready "
        "to resolve once world time reaches its own end_time (start_time + duration) -- "
        "not the acting entities (a car, a door, ...) they concern, which carry no "
        "schedule of their own. An event usually also carries involved_entity links "
        "naming who/what it concerns.\n\n"
        "Call start_world once, at the beginning, to open or seed a save. Then call "
        "advance_simulation with no arguments: it pauses on every such event, in two or three "
        "separate steps -- decide (NPC-controlled events only), then resolve, then plan -- "
        "each returning {\"status\": \"input_required\", \"prompt\": ..., \"step\": "
        "\"decide_event\" or \"resolve_event\" or \"plan_events\", \"responder\": "
        "\"host\" or \"subagent\", \"resume_token\": ...}. `step` names exactly which of the "
        "three below is asking, so you don't have to infer it from `prompt`'s own wording. "
        "If responder is \"host\", decide "
        "what happens yourself, from your own context. If it's \"subagent\", the prompt itself "
        "asks you to delegate to your own isolated subagent mechanism (e.g. an Agent/Task "
        "tool) instead of answering inline -- follow that instruction rather than answering "
        "directly. Either way:\n"
        "- On a decide prompt (an NPC's own turn only -- a human-voiced character's event "
        "skips straight to resolve, since their action is already whatever they told you): "
        "the prompt already includes everything that NPC currently perceives -- decide their "
        "action from that alone, do not also call view_registry/view_entity to see more than "
        "you were given, and do NOT call update_registry -- just describe the action in plain "
        "text; the resolve step, next, is what actually records it.\n"
        "- On a resolve prompt: for an NPC whose decide step already ran, the prompt tells you "
        "what it decided -- record that decision's consequences, don't re-decide it. For a "
        "human-voiced character's own event, the prompt itself will say so and remind you to "
        "actually ask the player what they did if you don't already know it from this "
        "conversation -- don't invent or assume their action. Either way, ground what you "
        "record and what you narrate back to the player in that character's own bounded view "
        "-- look up what they'd actually perceive (nearby entities, their own current "
        "description/state) rather than everything the registry happens to know, the same "
        "restriction an NPC's decide step gets, just enforced by you instead of a separate "
        "call. Look up whatever "
        "else you need (view_entity/view_registry, including the event's own involved_entity "
        "links) to work out what happened, then record it yourself via update_registry -- "
        "that event's own `outcome` (a natural-language description, plus whether this leaves "
        "it \"complete\" or \"interrupted\"), that event's own `event_state` transition, and "
        "anything it changes about the entities it involves.\n"
        "- On a plan prompt: decide whether anything new needs to be scheduled as a result, "
        "and if so create it yourself via update_registry -- one or more new `event` entities, "
        "each with its own start_time/duration/event_state/involved_entity. If nothing "
        "follows from this event, just say so; \"nothing new\" is a normal answer, not a case "
        "to avoid.\n\n"
        "Either way, call advance_simulation again with that exact resume_token and a short "
        "answer describing what you just recorded. It will keep asking (a new resume_token "
        "each time -- always use the one from the latest result) until either it needs you "
        "once more or the schedule empties (\"status\": \"done\").\n\n"
        "update_registry's entity-first YAML needs each component as a list item (a leading "
        "`- `) to attach to an existing aliased entity -- `car_a:\\n    - event_state:\\n        "
        "value: complete` merges into the same car_a already in the registry. The same content "
        "as a bare mapping (no `- `) is silently accepted with no error, yet records nothing "
        "at all -- always use the list form.\n\n"
        "`description` is a current-value component: a new write becomes the entity's "
        "current one, both for view_entity and for the save's exported YAML (older writes "
        "stay recorded as history — view_entity still shows all of them). Write the whole "
        "updated description each time, not a diff.\n\n"
        "Use view_registry/view_entity to look up what's already known before deciding — "
        "don't invent entities or details nothing has established."
    ),
    # FastMCP's default ("INFO") logs a line for every incoming request
    # (e.g. "Processing request of type CallToolRequest") -- harmless but
    # drowns out an interactive client's own output (e.g. a driving
    # notebook's cell output) with per-tool-call noise. WARNING+ still
    # surfaces anything that actually needs attention.
    log_level="WARNING",
)

# The line above alone doesn't take effect: `from story_simulator import core`
# transitively imports `emc2p.mcp_server` (for its RegistrarSessions class),
# whose own module-level `FastMCP("emc2p", ...)` -- unused here, just a side
# effect of the import -- already calls `logging.basicConfig(level="INFO")`
# first. `logging.basicConfig` is a no-op once the root logger already has a
# handler, so this module's own `log_level="WARNING"` above silently loses
# that race. Setting the root logger's level directly, after both FastMCP
# constructions have already run, is what actually wins.
logging.getLogger().setLevel(logging.WARNING)


@server.tool(description=core.start_world.__doc__)
def start_world(
    save_dir: str, ctx: Context, scenario_dir: str | None = None, client_trace_path: str | None = None
) -> str:
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.start_world"}
    return core.start_world(ctx.request_context.session, save_dir, scenario_dir, client_trace_path)


@server.tool(description=core.advance_simulation.__doc__)
async def advance_simulation(ctx: Context, resume_token: str | None = None, answer: str | None = None) -> dict:
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.advance_simulation"}
    return await core.advance_simulation(ctx.request_context.session, resume_token, answer)


# Mounts view_registry/view_entity/update_registry/consolidate_review --
# see this module's own docstring for why open_registry is excluded.
core.registrar_sessions.mount(server, exclude={"open_registry"})


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
