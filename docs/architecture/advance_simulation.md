# Architecture diagram

Entities reachable from `mcp_server.advance_simulation` by following `calls` edges outward (the root is highlighted); grouped into one subgraph per source file, except where noted next. An entity that itself makes two or more calls gets its call targets pulled into their own subgraph instead, chained top to bottom by dotted arrows in the order it actually calls them (skipping over any unresolved call in between). A solid `calls` arrow landing on a node inside such a subgraph is drawn to the subgraph's own boundary instead, but always starts from the specific node making the call, even if that node is itself inside a subgraph. One call with one destination stays a plain arrow -- there's no order to show.

```mermaid
flowchart TB
    subgraph sg0["config"]
        n14["event_responder"]
    end
    subgraph sg1["core"]
        n1["advance_simulation"]
        n6["_encode_token"]
        n13["safe_view_current"]
    end
    subgraph sg2["mcp_server"]
        n0["advance_simulation"]
    end
    subgraph seq1["advance_simulation"]
        n4["_get_registrar"]
        n5["_resolve_args"]
        n3["_run_event_loop"]
        n2["_wrap_loop_result"]
        n4 -.-> n5
        n5 -.-> n3
        n3 -.-> n2
    end
    subgraph seq3["_run_event_loop"]
        n9["pop_event"]
        n7["is_event_valid"]
        n8["process_event"]
        n9 -.-> n7
        n7 -.-> n8
    end
    subgraph seq4["process_event"]
        n11["advance_clock"]
        n12["resolve_event"]
        n10["plan_events"]
        n11 -.-> n12
        n12 -.-> n10
    end
    n0 --> n1
    n1 --> seq1
    n2 --> n6
    n3 --> seq3
    n8 --> seq4
    n9 --> n13
    n10 --> n14
    n12 --> n14
    class n0 rootNode
    classDef rootNode fill:#f96,stroke:#333,stroke-width:3px
```
