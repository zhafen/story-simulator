# story-simulator

An MCP for event-driven simulations powered by LLMs.

*For a reliable reference example of event-driven simulation, see Sedgewick & Wayne's
[6.1 Event-Driven Simulation](https://algs4.cs.princeton.edu/61event/) (Algorithms, 4th Edition).*

story-simulator is an MCP server for a text simulation whose world state lives in a structured
entity/component registry ([`emc2p`](emc2p)), not in whatever AI narrates it. There's no built-in
agent loop — you play by connecting an MCP-aware chat client (Claude Code, Claude Desktop, or
similar) to the server below and talking to it; that client's own replies *are* the narration.

> **Character/NPC/terrain/physics/spatial-perception tools are currently shelved.**
> `perceive`, `advance_npc_turn`, `generate_terrain`, and `resolve_physics` — and the model API
> key they needed — have been moved to [`shelved/`](shelved) pending a rewrite; see
> [`docs/architecture.md`](docs/architecture.md). What's live today is the base event loop:
> `start_world`, `advance_simulation`, `view_registry`, `view_entity`, `update_registry` — every
> due entity resolves via the connected host deciding directly (`responder="host"`, the default)
> or delegating to its own isolated subagent (`responder="subagent"`, opt in with
> `STORY_SIM_RESPONDER=subagent`) — no separate model call of story-simulator's own either way.

## Quick start

1. Have a database available for the world registry — `emc2p`'s registry connects via `ibis`, so
   any backend it supports works, as long as separate processes can hold their own concurrent
   connection to it (unlike a single-file embedded database), which is what lets the registry
   stay readable while a session is still live. Defaults to Postgres —
   `postgresql://postgres:postgres@localhost:5432/postgres` (matching GitHub Actions' `postgres:`
   service container, so CI needs no override); point elsewhere with:
   ```
   export STORY_SIM_DATABASE_DSN=postgresql://user:pass@host:5432/dbname
   ```
   Each `save_dir` gets its own schema within that database, created automatically on first
   `start_world`.
2. Configure your MCP-aware client to launch `uv run story-simulator-mcp` (world state +
   event-loop tools). Optionally, a separately-installed [`iacs`](https://github.com/zhafen/iacs)
   MCP server (`iacs-mcp`) can be connected alongside it for entity-format guidance —
   `describe_format`/`validate_yaml` — see [`docs/architecture.md`](docs/architecture.md); it's no
   longer vendored here since story-simulator only depends on `emc2p`, the generic registry engine.
3. Talk to it:
   ```
   you:   I want to play story-simulator. Please start up a world.
   agent: [calls start_world, view_registry] The world is ready. You are in a vast,
          empty expanse, with only a door in front of you.
   you:   I walk through the door.
   agent: [calls advance_simulation, decides what happens, records it via update_registry]
          You are now in a wide, empty field.
   ```
   The connected agent does the narrating and deciding itself — nothing above is
   story-simulator code running a loop.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full tool list, who plays which role,
and known follow-ups.

## Testing

```
uv run pytest
```
runs the full unit suite — fast, no external dependencies beyond the database from Quick start.
(`shelved/tests/` isn't collected — including its `@pytest.mark.live` end-to-end suite, which
spawned a real headless `claude` CLI session; see `shelved/` above.)
