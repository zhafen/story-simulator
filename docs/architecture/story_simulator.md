# Architecture diagram

Solid arrows are calls, dashed arrows are imports.

```mermaid
flowchart LR
    n0["story_simulator.config"]
    n1["story_simulator.core"]
    n2["story_simulator.keyed_subagent"]
    n3["story_simulator.mcp_server"]
    n4["story_simulator.resolve"]
    n1 --> n0
    n1 -.-> n0
    n1 -.-> n4
    n2 --> n0
    n2 -.-> n0
    n2 -.-> n1
    n3 --> n1
    n3 -.-> n1
```
