# Architecture diagram

Entities reachable from `mcp_server.advance_simulation` by following `calls` edges outward (the root is highlighted); grouped into one subgraph per source file, except where noted next. An entity that itself makes two or more calls gets its call targets pulled into their own subgraph instead, chained top to bottom by dotted arrows in the order it actually calls them (skipping over any unresolved call in between). A solid `calls` arrow landing on a node inside such a subgraph is drawn to the subgraph's own boundary instead, but always starts from the specific node making the call, even if that node is itself inside a subgraph. One call with one destination stays a plain arrow -- there's no order to show.

```mermaid
flowchart TB
    subgraph sg0["config"]
        n15["event_responder"]
    end
    subgraph sg1["core"]
        n1["advance_simulation"]
        n5["_load_pending"]
        n6["_save_pending"]
        n11["_next_time_stamp"]
    end
    subgraph sg2["mcp_server"]
        n0["advance_simulation"]
    end
    subgraph seq1["advance_simulation"]
        n2["_resolve_args"]
        n4["_run_event_loop"]
        n3["_wrap_loop_result"]
        n2 -.-> n4
        n4 -.-> n3
    end
    subgraph seq4["_run_event_loop"]
        n9["keyed_subagent_time_budget_seconds"]
        n10["pop_event"]
        n8["is_event_valid"]
        n7["process_event"]
        n9 -.-> n10
        n10 -.-> n8
        n8 -.-> n7
    end
    subgraph seq6["process_event"]
        n14["advance_clock"]
        n12["resolve_event"]
        n13["plan_events"]
        n14 -.-> n12
        n12 -.-> n13
    end
    n0 --> n1
    n1 --> seq1
    n2 --> n5
    n3 --> n6
    n4 --> seq4
    n6 --> n11
    n7 --> seq6
    n12 --> n15
    n13 --> n15
    class n0 rootNode
    classDef rootNode fill:#f96,stroke:#333,stroke-width:3px
```
