# story-simulator

An MCP for event-driven simulations powered by LLMs.

*For a reliable reference example of event-driven simulation, see Sedgewick & Wayne's
[6.1 Event-Driven Simulation](https://algs4.cs.princeton.edu/61event/) (Algorithms, 4th Edition).*

story-simulator is an MCP server for a text simulation whose world state lives in a structured
entity/component registry ([`iacs`](iacs)), not in whatever AI narrates it. There's no built-in
agent loop — you play by connecting an MCP-aware chat client (Claude Code, Claude Desktop, or
similar) to the server below and talking to it; that client's own replies *are* the narration.

> **Character/NPC/terrain/physics/spatial-perception tools are currently shelved.**
> `perceive`, `advance_npc_turn`, `generate_terrain`, and `resolve_physics` — and the model API
> key they needed — have been moved to [`shelved/`](shelved) pending a rewrite; see
> [`docs/architecture.md`](docs/architecture.md). What's live today is the base event loop:
> `start_world`, `advance_simulation`, `update_registry` — every
> due entity resolves via the connected host deciding directly (`responder="host"`, the default)
> or delegating to its own isolated subagent (`responder="subagent"`, opt in with
> `STORY_SIM_RESPONDER=subagent`) — no separate model call of story-simulator's own either way.
> Reading the registry (`view_entity`/`view_component`) is iacs-mcp's job, not
> story-simulator's own — see `docs/architecture.md`.

## Quick start

1. Have a database available for the world registry — `iacs`'s registry connects via `ibis`, so
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
2. Configure your MCP-aware client to launch two servers: `uv run story-simulator-mcp` (world
   state + event-loop tools) and `uv run iacs-mcp` (entity-format guidance — `describe_format`/
   `validate_yaml` — see [`docs/architecture.md`](docs/architecture.md) for why both are needed).
3. Talk to it:
   ```
   you:   I want to play story-simulator. Please start up a world.
   agent: [calls start_world, then iacs's load_database] The world is ready. You are in a vast,
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
