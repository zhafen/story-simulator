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

`view_registry`/`view_entity` are thin delegates to iacs's own Registrar
methods (`view_df`/`view_entity`), not independent reimplementations --
a prior version of each did reimplement the read/traversal logic itself,
which turned out to just duplicate what iacs's own `view_component`/
`view_entity` MCP tools already wrap. An even earlier iteration removed
these two tools entirely in favor of requiring iacs's own tools instead;
reverted after live evidence that a connected host reliably discovers and
uses tools on THIS server but has never once discovered or called a tool
on a separate one, however strongly nudged (see docs/manifest/history.yaml:
project_history.story_simulator_view_tools_reinstated_as_iacs_delegates).
Delegating (calling the same underlying Registrar object this server
already holds) avoids the original duplication without repeating that
discoverability problem.

This file is deliberately thin: every `@server.tool()` function below just
unpacks `ctx.request_context.session` into a plain session id and calls
straight into `story_simulator.core`, which owns the actual implementation
(including session state, Postgres bootstrap, world save I/O, and the event
loop itself). The docstrings here are what a connected host actually reads
(the MCP tool contract); `core.py`'s docstrings on the equivalently-named
functions describe the behavior itself.

Character/NPC/terrain/physics/spatial-perception behavior (`perceive`,
`advance_npc_turn`, `generate_terrain`, `resolve_physics`, and the
character-aware branch this file's event loop used to take) has been moved
out to `shelved/` (see `docs/architecture.md`) pending a rewrite -- not
deleted, and easy to pull back in piece by piece; see git history for
exactly what those looked like at removal.

The judgment resolver behind all of this (`story_simulator.resolve`) is
what lets `core.resolve_event` reach a real decision from any nesting depth
without every intervening function having to be a generator -- see that
module's docstring.

Structurally mirrors `iacs/iacs/mcp_server.py`: plain `@server.tool()`
functions, `server.run(transport="stdio")`.
"""

from __future__ import annotations

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
        "advance_simulation with no arguments: it pauses on every such event, in two separate "
        "steps -- resolve, then plan -- each returning "
        "{\"status\": \"input_required\", \"prompt\": ..., \"responder\": \"host\" or "
        "\"subagent\", \"resume_token\": ...}. If responder is \"host\", decide what happens "
        "yourself, from your own context. If it's \"subagent\", the prompt itself asks you to "
        "delegate to your own isolated subagent mechanism (e.g. an Agent/Task tool) instead of "
        "answering inline -- follow that instruction rather than answering directly. Either "
        "way:\n"
        "- On a resolve prompt: look up whatever you need (view_entity/view_registry, "
        "including the event's own involved_entity links) to work out what happened, then "
        "record it yourself via update_registry -- that event's own `outcome` (a "
        "natural-language description, plus whether this leaves it \"complete\" or "
        "\"interrupted\"), that event's own `event_state` transition, and anything it changes "
        "about the entities it involves.\n"
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
)


@server.tool()
def start_world(save_dir: str, ctx: Context, scenario_dir: str | None = None) -> str:
    """Open a world save for this session, seeding it from `scenario_dir` if it's empty.

    The loose seed *.yaml under scenario_dir is only ever merged into the
    registry the first time this save_dir is opened (a brand-new schema has
    no component types yet) — a resumed save's accumulated state already
    lives in the persisted registry, so reloading the seed YAML again on
    every start_world call would re-merge the same starting entities
    repeatedly.

    Args:
        save_dir: Directory holding (or to hold) this world's save data.
        scenario_dir: Starting scenario to seed a brand-new save_dir from
            (an EC directory, e.g. containing scenario.yaml). Defaults to
            story-simulator's plain default world (a player, a door, an
            empty expanse). Ignored if save_dir already has any save data.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.start_world"}
    return core.start_world(ctx.request_context.session, save_dir, scenario_dir)


@server.tool()
def view_registry(component_type: str, ctx: Context) -> str:
    """View all recorded data for one component type (e.g. "position", "object", "character").

    Covers both the starting scenario and everything recorded since, since
    it reads straight from the registry.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.view_registry"}
    return core.view_registry(ctx.request_context.session, component_type)


@server.tool()
def view_entity(entity_id: str, ctx: Context) -> str:
    """Return every recorded component instance for a specific entity.

    Args:
        entity_id: Entity hash, alias, or unambiguous path fragment (e.g.
            "player", "desk", or "journaling_desk.desk").
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.view_entity"}
    return core.view_entity(ctx.request_context.session, entity_id)


@server.tool()
def update_registry(yaml_string: str, ctx: Context) -> str:
    """Merge entity-first YAML into the world registry, run through the same ETL as save files.

    Args:
        yaml_string: Entity-first YAML content to merge in.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.update_registry"}
    return core.update_registry(ctx.request_context.session, yaml_string)


@server.tool()
async def advance_simulation(ctx: Context, resume_token: str | None = None, answer: str | None = None) -> dict:
    """Fast-forward through any events whose end_time has been reached,
    and pause whenever a turn needs input only outside story-simulator's
    own process can supply.

    The event-driven simulation (see `core.py`) -- world state is `event`
    entities, each ready to resolve once world time reaches its own
    end_time (start_time + duration), not the acting entities they
    concern. Every such event asks two separate responder calls in turn
    -- resolve (what happened), then
    plan (what, if anything, follows) -- each via responder="host" or
    "subagent" (see `config.event_responder`); expect two pauses per
    event, not one. No character/NPC concept at all. (A character-aware
    branch used to layer player/NPC turns on top of an earlier,
    next_due-based version of this loop; moved out to `shelved/` pending
    a rewrite -- see `docs/architecture.md`.)

    Call with neither argument to start (or continue after a prior call
    finished with nothing left scheduled). That, and every later call,
    returns either ``{"status": "done", "narration": ...}`` or
    ``{"status": "input_required", "prompt": ..., "responder": "host" or
    "subagent", "resume_token": ...}``. On the latter, decide what happens
    yourself if `responder` is "host", or follow `prompt`'s own instruction
    to delegate to an isolated subagent if it's "subagent" -- either way,
    record it yourself via update_registry (there's no structured return
    value this tool applies on your behalf), then call again with that
    exact `resume_token` and your `answer` -- no separate tool, and no
    server-side state to lose: `resume_token` carries everything needed to
    resume, so it survives an MCP disconnect/reconnect between calls too.

    Args:
        resume_token: The `resume_token` from this session's last
            `input_required` result, or omitted to start/continue fresh.
        answer: Your answer to that result's `prompt` -- what an event's
            resolution was, or what (if anything) it schedules next,
            recorded via update_registry before you answer. Omit `answer`
            itself along with `resume_token` on a fresh call.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.advance_simulation"}
    return await core.advance_simulation(ctx.request_context.session, resume_token, answer)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
