# story-simulator

story-simulator is an MCP server for a text simulation whose world state lives in a structured
entity/component registry ([`iacs`](iacs)), not in whatever AI narrates it. There's no built-in
agent loop — you play by connecting an MCP-aware chat client (Claude Code, Claude Desktop, or
similar) to the server below and talking to it; that client's own replies *are* the narration.

## Running the server

```
uv run story-simulator-mcp
```

Speaks MCP over stdio. Configure your client to launch this command (and, for entity-format
guidance while transcribing, `iacs-mcp` alongside it — see [`docs/architecture.md`](docs/architecture.md)
for why both are needed). Once connected, ask the client to call `start_world` to begin.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full tool list, who plays which role,
and how `advance_npc_turn` resolves an NPC's turn on its own.
