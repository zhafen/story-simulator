# Architecture

story-simulator is **just an MCP server**. There is no agent loop inside
this project — the loop is whatever MCP-aware client connects (a human's
chat agent, an automated harness, ...). story-simulator's job is to expose
good tools for playing a text simulation whose state lives in a structured
entity/component registry ([`iacs`](../iacs)), not in the connected agent's
own context.

What each tool must guarantee, what code satisfies it, and every open
follow-up are modeled as `requirement`/`solution` entities in
[`docs/manifest/story-simulator.yaml`](manifest/story-simulator.yaml), not
duplicated here as prose — load it with the iacs MCP server
(`load_manifest(["docs/manifest", "story_simulator"])`, since most solutions
now live as `__iacs__` metadata in code docstrings rather than in the YAML)
and run `run_dataflow("audit.requirement_coverage")`/`("audit.traceability")`
to check current status, or query `resolved_impact_cost` for a cost-vs-impact
read on what's still open.

## Who plays which role

```mermaid
flowchart LR
    Human(("Human player")) <--> Client["MCP-aware chat client<br/>(the narrator/game master)"]
    Client -- "start_world, perceive,<br/>view_registry, view_entity,<br/>update_registry,<br/>generate_terrain, resolve_physics,<br/>advance_npc_turn" --> Server["story-simulator-mcp"]
    Client -- "describe_format,<br/>validate_yaml" --> Iacs["iacs-mcp"]
    Server -- "reads/writes" --> DB[("registry database<br/>(one schema per save_dir)")]
    Server -- "generate_terrain /<br/>resolve_physics calls" --> LiteLLM
    LiteLLM --> Provider[("Anthropic, OpenAI, Ollama, ...")]
```

For a human player, narration is just the connected agent's own replies —
nothing in story-simulator narrates *for* it. `iacs-mcp` (attached alongside,
unmodified) stays the format/validation reference — `describe_format`/
`validate_yaml` — since it has no way to see story-simulator's live,
accumulating registry state (its own `load_manifest` only re-reads static
files).

## `advance_npc_turn`: a tool that calls other tools

Nested tool calls are how an autonomous NPC turn gets resolved without a
human or connected chat agent driving it — the outer caller sees one opaque
tool call; internally it decides, then runs its own small tool-calling loop
(`agents.run_tool_loop`) that can call
`generate_terrain`/`resolve_physics`/`update_registry` in-process before
returning.

```mermaid
sequenceDiagram
    participant Caller as Connected agent
    participant Tool as advance_npc_turn
    participant Decide as npc.yaml (complete)
    participant Narrate as npc_resolver.yaml (run_tool_loop)

    Caller->>Tool: advance_npc_turn(npc_alias)
    Tool->>Tool: perceive(npc_alias) — in-process
    Tool->>Decide: what does npc_alias do?
    Decide-->>Tool: decided action text
    Tool->>Narrate: resolve this action
    alt narration needs terrain
        Narrate->>Tool: generate_terrain(description)
    end
    alt narration needs physics
        Narrate->>Tool: resolve_physics(scenario)
    end
    Narrate->>Tool: update_registry(yaml_string)
    Narrate-->>Tool: summary text
    Tool-->>Caller: "npc_alias: <action>\n<summary>"
```
