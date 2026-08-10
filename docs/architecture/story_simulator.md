# Architecture diagram

Solid arrows are calls, dashed arrows are imports.

```mermaid
flowchart LR
    n0["config"]
    n1["core"]
    n2["mcp_client"]
    n3["mcp_server"]
    n4["resolve"]
    n3 --> n0
    n3 -.-> n0
    n3 --> n1
    n3 -.-> n1
    n3 --> n4
    n3 -.-> n4
```
