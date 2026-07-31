# story-simulator

story-simulator is an MCP server for a text simulation whose world state lives in a structured
entity/component registry ([`iacs`](iacs)), not in whatever AI narrates it. There's no built-in
agent loop — you play by connecting an MCP-aware chat client (Claude Code, Claude Desktop, or
similar) to the server below and talking to it; that client's own replies *are* the narration.

## Quick start

1. Set a model API key the `generate_terrain`/`resolve_physics`/`advance_npc_turn` tools can use
   (Anthropic by default — see `.env.example`; any other LiteLLM-supported provider works too,
   configured via that provider's own standard env var):
   ```
   export STORY_SIM_ANTHROPIC_API_KEY=sk-...
   ```
2. Have a database available for the world registry — `iacs`'s registry connects via `ibis`, so
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
3. Configure your MCP-aware client to launch two servers: `uv run story-simulator-mcp` (world
   state + narrative tools) and `uv run iacs-mcp` (entity-format guidance — `describe_format`/
   `validate_yaml` — see [`docs/architecture.md`](docs/architecture.md) for why both are needed).
4. Talk to it:
   ```
   you:   I want to play story-simulator. Please start up a world.
   agent: [calls start_world, view_registry] The world is ready. You are in a vast,
          empty expanse, with only a door in front of you.
   you:   I walk through the door.
   agent: [calls perceive, maybe generate_terrain/resolve_physics, then update_registry]
          You are now in a wide, empty field.
   ```
   The connected agent does the narrating and tool-calling itself — nothing above is
   story-simulator code running a loop.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full tool list, who plays which role,
how `advance_npc_turn` resolves an NPC's turn on its own, and known follow-ups.
