# CLAUDE.md - AI Assistant Instructions for story-simulator

## Project Overview

story-simulator is an MCP server exposing a text-simulation game master's
tools (`start_world`, `perceive`, `update_registry`, ...). World state lives
in a Postgres-backed `iacs` registry, not in this project's own process
memory — see `docs/architecture.md` for the full picture.

Every `update_registry` call (including the NPC turn's own internal one)
re-exports the registry's state to two directories, not the source of truth
but both current as of the last turn:
- `save_dir/world/`: current state, collapsed — a time_dimension'd
  component type (`description`, `state`, `position`) shows only its
  current row per entity, not every historical restatement of it.
- `save_dir/world_history/`: the same content, uncollapsed — every row
  ever recorded for every entity, full change history. The registry itself
  always keeps full history regardless (nothing is ever deleted, only what
  the collapsed export shows), but that history would otherwise only exist
  in Postgres; this is what makes it survive in the repo too.

These are directories, not fixed filenames, because `export_manifest`
writes one EC yaml file per original source filepath — currently that's
always exactly one file per directory (every `registrar.update()` call
across this project shares `WORLD_FILE_ID` as its source key), but nothing
about the save format assumes that stays true. A save can be split across
as many files as its author wants (nested however, e.g. one per location),
matching iacs's own principle of letting an EC source be organized however
you wish rather than one monolithic file — `start_world`'s loader recurses
into whichever directory it picks (see below) rather than assuming a
single file lives there.

The save's original seed (`scenario.yaml`, or wherever `scenario_dir`
pointed) is still frozen turn-zero data and never updated by either export
— if you're reading a save's current state, read `save_dir/world/`, not
the seed file (and not `save_dir/world_history/`, unless you actually want
the full change log rather than what's current).

`start_world`'s first-open loader picks exactly one of `world_history/` /
`world/` / a recursive glob of everything under `save_dir`, in that
explicit preference order, rather than combining more than one at once:
concatenating redundant sources risks silently discarding data (YAML's
last-key-wins on the resulting duplicate top-level keys picks whichever
row happened to sort last, replacing rather than merging). `world_history/`
is a strict superset of `world/`'s rows, which are in turn a strict
superset of the original seed's own content (still present as each
entity's earliest historical row), so preferring the fullest one loses
nothing. The final fallback — recursing the whole `save_dir` when neither
export directory exists yet — is what still lets a pristine,
never-yet-opened `scenario_dir` be organized across multiple files at
arbitrary depth (not just one flat `scenario.yaml`), same as before this
directory-based redesign.

(Earlier revision of this same fix used single fixed filenames,
`world.yaml`/`world_history.yaml`, instead of directories — replaced
because a fixed filename can't be split across multiple files, which
defeated the point of a save being freely organizable EC data in the first
place, and because a genuinely multi-file `scenario_dir` would have lost
that freedom the moment it was first opened and re-exported back to a
single file.)

**`data/living_world` is still not a pristine `scenario_dir` template.**
It holds `scenario.yaml` (the original turn-zero seed) plus
`world/`/`world_history/` (a real playthrough's accumulated state,
committed deliberately so that progress wasn't only living in this
session's ephemeral Postgres). To **continue** that playthrough, open
`data/living_world` as `save_dir` itself, with no separate `scenario_dir`.
Do **not** pass it as `scenario_dir` to seed a different, new `save_dir` —
`_seed_save_dir` would copy `scenario.yaml` and both export directories
into the new location, and the loader would then deterministically pick
`world_history/` there too, so the new "fresh" save would still start with
this playthrough's full history already merged in. A genuinely fresh
living-world playthrough needs a different, currently-nonexistent pristine
source.

## Prefix in-world narration with `> narrator:`

When narrating a turn's outcome directly to the player (step 3 of the
per-action loop below), prefix that in-world text with `> narrator:` so
it's visually distinguishable from ordinary conversational replies. This
applies only to the actual narration text, not to out-of-character asides
or status updates.

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

## Define a component type's schema before improvising one through gameplay YAML

iacs doesn't require pre-registering a component type — `update_registry`
will happily accept a component name nobody ever declared, typing its
fields from whatever the YAML shorthand implies. That's how `state` (a
door's open/closed status) ended up undefined for most of a playtest
session: real, working gameplay data with no `description`, no field
types, and critically no `time_dimension` flag, so it silently
accumulated an ever-growing, undifferentiable history instead of
resolving to one current value the way `position`/`description` do.

If a turn's narration needs a component type that isn't already in
`manifest/builtins.yaml` (check there and in `iacs/iacs/builtins/
components.yaml` first — most needs are already covered, e.g. `state` for
a short current-status word/phrase, `description`/`appearance` for
current-look text, `size` for perceptibility), define it properly in
`manifest/builtins.yaml` before using it: a top-level entry with its own
`description` explaining what it's for, a `component_type` tag, and a
`field:` block declaring each field's name/type/description — and, if it's
a "current value" kind of fact rather than an accumulating log, a nullable
`time` field flagged `time_dimension: true`, matching `position.time`'s/
`state.time`'s pattern. This only applies when you actually have write
access to the repo (a Claude Code session like this one); a narrator
connected only through the MCP tool surface has no way to act on it and
should just use what's already defined.
