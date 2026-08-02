# CLAUDE.md - AI Assistant Instructions for story-simulator

## Project Overview

story-simulator is an MCP server exposing a text-simulation game master's
tools (`start_world`, `perceive`, `update_registry`, ...). World state lives
in a Postgres-backed `iacs` registry, not in this project's own process
memory — see `docs/architecture.md` for the full picture.

Every `update_registry` call (including the NPC turn's own internal one)
re-exports the registry's current state to `save_dir/world.yaml` — a
generated, read-only mirror, not the source of truth, but current as of the
last turn. The save's original seed (`scenario.yaml`, or wherever
`scenario_dir` pointed) is still frozen turn-zero data and never updated —
if you're reading a save's YAML for current state, read `world.yaml`, not
the seed file.

**`data/living_world` is no longer a pristine `scenario_dir` template.**
It now holds both `scenario.yaml` (the original turn-zero seed) and
`world.yaml` (a real playthrough's accumulated state, committed
deliberately so that progress wasn't only living in this session's
ephemeral Postgres). To **continue** that playthrough, open
`data/living_world` as `save_dir` itself, with no separate `scenario_dir`.
Do **not** pass it as `scenario_dir` to seed a different, new `save_dir`
anymore — `_seed_save_dir` would copy both files into the new location,
and `start_world`'s first-open loader concatenates every `*.yaml` file's
raw text into one document before parsing, so the new "fresh" save would
silently start with this playthrough's full history already merged in
(YAML's last-key-wins on the resulting duplicate top-level keys happens to
make this non-destructive today only because `world.yaml` sorts after
`scenario.yaml` and is already a superset of it — not a guaranteed
invariant, just how it currently shakes out). A genuinely fresh living-world
playthrough needs a different, currently-nonexistent pristine source.

## Reloading `story-simulator-mcp` after editing its code

`.mcp.json` spawns `story-simulator-mcp` once, as a long-lived stdio
subprocess, when this session's MCP connection is established. Python
doesn't hot-reload: editing `story_simulator/mcp_server.py` (or anything it
imports) has **no effect on an already-running session** until that
subprocess restarts — calling `mcp__story-simulator__*` tools after an edit
silently keeps exercising the pre-edit code.

**Fix, verified working (no session restart needed):**

```bash
pkill -f story-simulator-mcp
```

The harness auto-respawns it fresh on the very next `mcp__story-simulator__*`
tool call, picking up current source. World state is untouched (it lives in
Postgres, not this process), but the session-scoped registrar cache resets,
so call `start_world` again once after killing it.

Confirmed live: killed the subprocess, stopped Postgres, then called
`start_world` through the reloaded connection with no manual `service
postgresql start` — it self-healed via the (freshly loaded)
`_ensure_postgres_running()` fix, proving the kill actually picks up new
code rather than just timing out to the same behavior.

For validating plain Python logic changes (not the live MCP tool surface
itself), prefer `pytest`/a fresh `python -c` invocation over this — it's
lower-friction and always reads current disk state, same reasoning, less
ceremony.

## Recovering from an idle-triggered MCP disconnect mid-play

A player stepping away between turns for long enough is a routine,
expected event, not an error state — the story-simulator MCP connection
can drop while they're gone and reconnect on its own once they're back.
Handle both failure shapes below without asking the player what to do;
they don't need to know any of this happened.

- A `mcp__story-simulator__*` call fails with `"No world open for this
  session yet — call start_world first."` The session-scoped registrar
  cache reset (a fresh subprocess), but world state itself is untouched —
  it lives in Postgres, not that process. Silently call `start_world`
  again with the same `save_dir` (and `scenario_dir`, if this is the
  session's first-ever open) already established earlier in the
  conversation, then retry the action that failed.
- The server disconnects entirely (its tools vanish from the deferred
  list; a system notice says the MCP server disconnected). There's no tool
  to force a reconnect — just wait. It comes back on its own (confirmed
  repeatedly, sometimes within the same exchange); the moment a "deferred
  tools available again" notice arrives, resume the pending player action
  immediately in the same turn instead of waiting for them to re-prompt.

Keep the save's `save_dir` (and `scenario_dir`) in mind for exactly this
reason — the whole recovery path depends on being able to reopen the same
save without asking the player to repeat it.
