"""MCP server exposing story-simulator's world-state and event-loop tools.

story-simulator is *just* this server today -- no in-process agent loop
lives here. `advance_simulation` runs ONE event-driven simulation loop (one
function per step -- see `core._run_event_loop`), built entirely on
`story_simulator.core`'s base `pop_event`/`predict_next_event`/`push_event` --
see `core.py`'s own docstring for what that guarantees. The loop
fast-forwards through anything it can resolve on its own, and pauses
whenever a turn needs input only the connected host can supply -- an
entity's own resolution -- handing control back to whatever MCP-aware host
is connected (a human's chat agent, an automated harness, ...). That host
decides what happens itself (`responder="host"`, the default) or is asked
to delegate to its own isolated subagent mechanism instead
(`responder="subagent"`, opt in via STORY_SIM_RESPONDER -- see
`story_simulator.config.event_responder`) -- see `advance_simulation`'s own
`responder` field -- then calls `advance_simulation` again with its decision
(recorded via `update_registry`) and the `resume_token` it was given, to
resume the loop -- Multi Round-Trip Requests (MRTR, MCP spec 2026-07-28),
not a second dedicated tool. `view_registry`/`view_entity`/`update_registry`
remain directly callable too, for anything outside that loop.

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
        "run as an event-driven simulation (one entity due at a time, scheduled by its "
        "own next_due) rather than a fixed per-turn loop.\n\n"
        "Call start_world once, at the beginning, to open or seed a save. Then call "
        "advance_simulation with no arguments: it pauses on every due entity in turn, "
        "returning {\"status\": \"input_required\", \"prompt\": ..., \"responder\": \"host\" or "
        "\"subagent\", \"resume_token\": ...}. If responder is \"host\", decide what happens "
        "yourself, from your own context. If it's \"subagent\", the prompt itself asks you to "
        "delegate to your own isolated subagent mechanism (e.g. an Agent/Task tool) instead of "
        "answering inline -- follow that instruction rather than answering directly. Either "
        "way, call advance_simulation again with that exact resume_token and the answer to "
        "resume the loop. State the outcome and end your answer with a line formatted exactly "
        "as `next_due_in: <seconds>` if this entity has more to do, or omit that line if it's "
        "finished. It will keep asking (a new resume_token each time -- always use the one "
        "from the latest result) until either it needs you once more or the schedule empties "
        "(\"status\": \"done\").\n\n"
        "Record what happened yourself via update_registry (new positions, new entities, "
        "changed details — reusing existing aliases; attach new data to an existing entity "
        "via a `same_as` component rather than creating a disconnected duplicate). "
        "`description` and `state` are both current-value components: a new write becomes "
        "the entity's current one, both for view_entity and for the save's exported YAML "
        "(older writes stay recorded as history — view_entity still shows all of them). "
        "Write the whole updated description each time, not a diff, and use `state` for a "
        "short current status word or phrase (e.g. a door being \"open\") rather than folding "
        "it into the description text.\n\n"
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
    """Fast-forward through any due entities, and pause whenever a turn
    needs input only outside story-simulator's own process can supply.

    The base event-driven simulation (see `core.py`) -- every due entity
    resolves via responder="host" or "subagent" (see
    `config.event_responder`), no character/NPC concept at all.
    (A character-aware branch used to layer player/NPC turns on top of
    this; moved out to `shelved/` pending a rewrite -- see
    `docs/architecture.md`.)

    Call with neither argument to start (or continue after a prior call
    finished with nothing left scheduled). That, and every later call,
    returns either ``{"status": "done", "narration": ...}`` or
    ``{"status": "input_required", "prompt": ..., "responder": "host" or
    "subagent", "resume_token": ...}``. On the latter, decide what happens
    yourself if `responder` is "host", or follow `prompt`'s own instruction
    to delegate to an isolated subagent if it's "subagent" -- either way,
    call again with that exact `resume_token` and your `answer` -- no
    separate tool, and no server-side state to lose: `resume_token` carries
    everything needed to resume, so it survives an MCP disconnect/reconnect
    between calls too.

    Args:
        resume_token: The `resume_token` from this session's last
            `input_required` result, or omitted to start/continue fresh.
        answer: What happens for the entity that result's `prompt` asked
            about (optionally ending with a `next_due_in: <seconds>` line
            -- omit it if there's nothing further to happen). Omit `answer`
            itself along with `resume_token` on a fresh call.
    """
    __iacs__ = {"solution of": "story_simulator_mission.tool_catalog.advance_simulation"}
    return await core.advance_simulation(ctx.request_context.session, resume_token, answer)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
