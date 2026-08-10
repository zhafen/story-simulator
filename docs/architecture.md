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

## The event-driven turn loop

Turns aren't a fixed round-robin over every character — they're scheduled,
Sedgewick & Wayne style (*Algorithms*, 4th ed., §6.1 Event-Driven
Simulation): every entity carries its own `next_due` time in the registry,
and the loop only ever pops whichever entity is due soonest, discarding
stale events rather than replaying them. `predict_event`/`push_event` is
the same function at both call sites in the diagram below — scheduling a
brand-new entity's first event and rescheduling after one resolves are the
same operation, not two.

`story_simulator/core.py` holds this event-loop kernel (`pop_event`,
`is_event_valid`, `advance_clock`, `predict_event`, `push_event`).
`story_simulator/mcp_server.py` holds the turn-processing layer that zooms
into whichever event `core.py` just popped (`process_event`,
`character_communication`, `resolve_event`, `update_data`), which in turn
loops `select_character`/`narrate_to_character`
(`story_simulator/spatial.py`) with `get_character_input`
(`story_simulator/mcp_server.py`) until that character's due action is
fully decided.

```mermaid
flowchart TD
    subgraph Turn["Process event"]
        direction TD
        G[Character communication] --> F[Resolve event]
        F --> D[Update data]
    end

    subgraph Comm["Character communication"]
        direction TD
        SC[Select character] --> NC[Narrate to character]
        NC --> GI[Get character input]
        GI --> SC
    end

    subgraph Event["Event-driven simulation (Sedgewick & Wayne)"]
        direction TD
        I1[Predict events] --> I2[Push to queue]
        I2 -- next entity --> I1
        I2 --> L1[Pop event]
        L1 --> V{Valid?}
        V -- stale --> L1
        V -- valid --> ADV[Advance clock]
        ADV --> PROC[Process event]
        PROC --> PRED[Predict next]
        PRED --> PUSH[Push events]
        PUSH --> L1
    end

    PROC -. zooms into .-> Turn
    G -. zooms into .-> Comm
    PRED -. same function as .-> I1
    PUSH -. same function as .-> I2
```

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
