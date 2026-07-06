# Plan: `test_startup_one_loop_save`

Research notes and implementation plan for making
`tests/test_human_validated.py::test_startup_one_loop_save` pass.

**Status: implemented.** Everything below except the live test run itself is
done — see "Implementation notes" at the end for what landed and how it
differs from the plan, and "Remaining blocker" for what's still needed to run
the live test.

## The task (as given)

1. Create the loop inside `EnsembleWorld` that loops through different agents
   and systems.
2. Create the Archivist agent (currently just an abstract `record()` method).
3. Test the Archivist's ability to transcribe descriptions into iacs EC files,
   with the help of the iacs MCP.
4. Enable `EnsembleWorld` to accept a `world_dir`/`save_dir` containing its
   save data.

## The test, and a confirmed bug in it

```python
def test_startup_one_loop_save():
    save_dir = DATA_DIR / "test_save"
    w = EnsembleWorld(save_dir=save_dir)
    p = Interpreter(EnsembleWorld())          # <-- BUG: fresh world, not `w`

    p.input("I look around. What do I see?")

    a = Architect.from_manifest(save_dir)
    assert a.get("position").count() >= 2
    assert a.get("origin").count() == 1
    assert (characters := a.get("character")).count() == 1
    assert characters.filter(characters.interaction_type == "player").count()
    assert (objects := a.get("object")).count() >= 1
    assert objects.filter(objects.type.contains("door")) == 1
    assert a.get("appearance").count() >= 2
```

`w` (the `EnsembleWorld` with `save_dir` set) is built but never used — the
`Interpreter` drives a second, separate `EnsembleWorld()` with no `save_dir`.
As written, nothing would ever write to `save_dir`.

**Confirmed with the user: this is a typo.** Fix line to:

```python
p = Interpreter(w)
```

This is a one-line fix to `tests/test_human_validated.py`, to make alongside
the implementation.

## Key findings about `iacs` (installed at `.venv/lib/python3.12/site-packages/iacs`)

- **No schema pre-registration needed.** Component types (`position`,
  `character`, `object`, `appearance`, `origin`, ...) do **not** need to be
  declared anywhere in advance. `iacs.dataflows.etl.load_manifest.component_tables`
  groups rows by whatever `component_type` strings appear in the entity-first
  YAML itself. Field validation/defaults (via `((field))` components) are
  optional extras layered on top, not a precondition for `Architect.get(...)`
  or `.filter(...)` to work. So the Archivist just needs to write valid
  entity-first YAML using those component names/fields; no separate "game
  schema" manifest is required for the test to pass.
- **Entity-first YAML format** (see
  `iacs/iacs_manifest/format_guide.yaml` and `iacs/builtins/components.yaml`):
  - Top-level keys are entity names; a list value is a flat entity (list of
    component items); a dict value is a nested entity (sub-entities +
    `data:` key for the entity's own components).
  - Component item forms: bare string = tag; `{comp: scalar}` = sets `value`
    field; `{comp: {field: val, ...}}` = sets named fields.
  - Example relevant to this test:
    ```yaml
    player:
        - position: {x: 0, y: 0}
        - origin
        - character: {interaction_type: player}
        - appearance: {value: "a traveler, worn coat"}
    door:
        - position: {x: 1, y: 0}
        - object: {type: wooden door}
        - appearance: {value: "a heavy wooden door"}
    ```
  - `Architect.from_manifest(dir)` recursively loads all `*.yaml`/`*.yml`
    files under `dir` (plus iacs builtins, always).
- **`Architect` / `Registry`** (`iacs/architect.py`, `iacs/registry.py`):
  `Architect.from_manifest(path)` runs the full ETL (load → validate →
  derive) and returns component tables as ibis `Table`s via `.get(component_type)`.
  `a.get("character").filter(...)`, `.count()` etc. are plain ibis operations.
- **iacs MCP server** (`iacs/mcp_server.py`, registered in this repo's
  `.mcp.json` as a **local stdio** process: `uv run iacs-mcp`) exposes:
  `get_manifest_path`, `load_manifest(manifest_paths)`,
  `list_component_types`, `view_component`, `view_entity`, `run_dataflow`,
  `refresh` (writes normalized EC YAML back to each file's *original* path,
  round-tripping through validate/derive), `describe_format` (returns the
  format-guide text — useful as few-shot context for an LLM), `validate_yaml`
  (validates a raw YAML string via a temp file, doesn't persist it).
  **There is no "write a new EC file" tool.** The Archivist has to write the
  YAML file itself (plain filesystem write) and can optionally use
  `validate_yaml` before writing and `load_manifest` + `refresh` after, to
  normalize formatting/derived fields in place.

## Design decisions (confirmed with user)

1. **Test bug**: fix `Interpreter(EnsembleWorld())` → `Interpreter(w)`.
2. **Archivist architecture**: a *local* tool-use loop, not the hosted
   Anthropic Agents/Sessions platform that `AgentWorld` uses. Reasoning: the
   hosted `beta.agents` API only accepts MCP servers reachable by **URL**
   (`BetaRequestMCPServerURLDefinitionParam` / `BetaManagedAgentsURLMCPServerParams`
   in the `anthropic` SDK types) — it cannot attach our local stdio
   `iacs-mcp` subprocess. So the Archivist should:
   - Use `anthropic.Anthropic().messages.create(...)` directly (not
     `beta.sessions`), with a manual tool-calling loop.
   - Talk to the iacs MCP server as an **MCP client** using the official
     `mcp` python package (`mcp-1.28.1`, already installed — pulled in
     transitively, add explicitly to `pyproject.toml` deps), via
     `mcp.client.stdio` spawning `uv run iacs-mcp` (or reusing this repo's
     `.mcp.json` command), translating the MCP tool list
     (`tool.inputSchema`) into Anthropic tool-param schemas, and dispatching
     `tool_use` blocks back to the MCP `call_tool`.
   - Add one more **local, non-MCP tool** for actually writing the EC YAML
     file into `save_dir` (since no MCP tool does this).
   - Point the MCP server at the world's `save_dir` — either via the
     `IACS_MANIFEST` env var when spawning the subprocess, or by calling the
     `load_manifest` tool with `save_dir` explicitly at the start of each
     `record()` call.
3. **Test execution**: implement fully, verify everything not requiring a
   live LLM call (MCP plumbing, file writing, unit tests with mocks), and
   leave the actual live run of `test_startup_one_loop_save` to a human with
   API access. **User chose to instead pause and add credentials before
   continuing** (see Blocker below).

## Planned code structure (not yet implemented)

- `story_simulator/world.py`:
  - `EnsembleWorld.__init__(self, world_soul=None, archivist=None, save_dir=None)`
    - Store `save_dir` (as `Path`, may be `None`).
    - If `archivist is None` and `save_dir is not None`, default to a
      concrete Archivist implementation constructed with `save_dir`.
    - Build `self.systems: list[Archivist]` (currently just the one
      archivist) so `respond()` loops over systems generically instead of
      hardcoding a single `self.archivist` call — this satisfies "loops
      through different agents and systems" and leaves room to add more
      systems later without changing `respond()`'s shape.
    - `respond()`: get `world_soul.respond(text)` first (it must run first
      since systems consume its output), then loop `for system in
      self.systems: system.record(text, response)`.
  - Keep `Archivist` as the existing abstract base (there's an existing test
    `test_archivist_cannot_be_instantiated` that must keep passing) and add a
    new concrete subclass, e.g. `IacsArchivist(Archivist)`, implementing
    `record()` with the local MCP tool-loop described above.
- Possibly a new `story_simulator/archivist.yaml` (+ maybe
  `archivist.test.yaml`) config file, mirroring the `agent.yaml` /
  `agent.test.yaml` pattern used for the World Soul, to hold the Archivist's
  system prompt (instructions to transcribe entities/components from the
  exchange text into EC YAML, using `describe_format` for the spec) and
  model choice.
- Possibly a new module (e.g. `story_simulator/mcp_client.py`) wrapping the
  stdio MCP session + tool-loop machinery, kept separate from `world.py` for
  testability (so it can be mocked in non-live unit tests the way
  `AgentWorld` is mocked in `tests/test_world.py`).

## Open questions for the next session

- Exact EC file naming/write strategy in `save_dir`: one growing file (e.g.
  `world.yaml`) that the Archivist edits turn over turn, vs. per-turn files.
  Multi-turn append-without-clobbering isn't exercised by this single-loop
  test but will matter once there's more than one turn.
- Whether to give the Archivist a cheap/fast default model (haiku, like
  `agent.test.yaml`) vs. reusing the World Soul's model.
- Whether `cli.py`'s `"ensemble"` world entry should grow a `--save-dir` flag
  for parity with the new constructor arg (not required by the stated task
  list, but likely nice-to-have).
- Need to add `mcp` as an explicit `pyproject.toml` dependency (currently
  only present transitively via `iacs`).

## Implementation notes (what actually landed)

- `story_simulator/world.py`: `IacsArchivist(Archivist)` implements the local
  tool-use loop as planned (`anthropic.Anthropic().messages.create` in a
  manual loop, capped at `MAX_ARCHIVIST_TOOL_TURNS = 8` round trips as a
  runaway-loop guard). `EnsembleWorld` gained `save_dir`, defaults its
  `archivist` to `IacsArchivist(save_dir)` when one isn't given, and loops
  over a generic `self.systems` list in `respond()`.
- `story_simulator/mcp_client.py`: `open_iacs_mcp_session(manifest_dir)` is an
  async context manager wrapping `mcp.client.stdio.stdio_client` +
  `mcp.ClientSession`, spawning `uv run iacs-mcp` with `IACS_MANIFEST` set to
  the world's `save_dir` and `cwd` pinned to the repo root. Exposes
  `.tools` (MCP tool list translated to Anthropic tool-param schemas) and
  `.call_tool(name, arguments)`.
- **EC file write strategy** (resolves the plan's open question): one file,
  `save_dir/world.yaml`, that the Archivist reads (`read_world_file` local
  tool) before composing the full updated content and overwriting
  (`write_world_file` local tool) — a "growing single file" rather than
  per-turn files, so multi-turn runs accumulate instead of clobbering.
  `refresh`/`load_manifest` are available to the model to normalize
  formatting but aren't required for the test's assertions.
- `story_simulator/archivist.yaml` / `archivist.test.yaml`: mirror the
  `agent.yaml` / `agent.test.yaml` pattern. Both use `claude-haiku-4-5`
  (resolves the plan's open question in favor of the cheap/fast model, since
  transcription doesn't need the World Soul's narrative model). The system
  prompt spells out the component schema the test expects
  (`position {x,y}`, `character {interaction_type}`, `object {type}`,
  `appearance {value}`, `origin` tag) since that's this game's actual data
  model, not a hypothetical.
- `mcp` added as an explicit `pyproject.toml` dependency; `cli.py`'s
  `"ensemble"` entry gained a `--save-dir` flag.
- Test bug fixed: `Interpreter(EnsembleWorld())` → `Interpreter(w)`.
- Unit tests added in `tests/test_world.py` (EnsembleWorld/save_dir/systems
  wiring, `IacsArchivist` read/write of `world.yaml`, and a full mocked
  tool-loop dispatch test using a fake MCP session + scripted
  `messages.create` responses) and `tests/test_cli.py` (`--save-dir`
  parsing). Full suite passes except the live test (see below).

## Remaining blocker

`test_startup_one_loop_save` is unmocked and needs a live Anthropic API key
plus network access (World Soul narration + Archivist tool-calling are both
real LLM calls). This session found that this remote environment reserves/
strips the `ANTHROPIC_API_KEY` name specifically (it collides with Claude
Code's own credential plumbing), so `AgentWorld`/`IacsArchivist` now read the
key via `story_simulator.config.resolve_anthropic_api_key()`, which checks
`STORY_SIM_ANTHROPIC_API_KEY` first (passed explicitly as `api_key=` to
`anthropic.Anthropic()`) and falls back to the SDK's normal
`ANTHROPIC_API_KEY` auto-discovery for local development. To run the live
test: add `STORY_SIM_ANTHROPIC_API_KEY` (holding a real key) to the
environment's variables and re-run
`pytest tests/test_human_validated.py::test_startup_one_loop_save`.
