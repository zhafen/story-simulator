# Shelved

The character/npc/physics/terrain/spatial-perception "optional modules"
(`story_simulator.config.ALL_MODULES` as of removal — see git history),
moved out of the active codebase rather than deleted or left half-gated
behind an unused toggle. Not part of the `story_simulator` package or
`tests/` (`pyproject.toml`'s `testpaths = ["tests"]` doesn't reach here,
and nothing in the live code imports from `shelved/`), so this is inert —
kept for reference and as a starting point for pulling any of it back in,
piece by piece, as needed. Some of the shelved tests' imports no longer
resolve as-is, since the code they import moved along with them; see each
file's own docstring.

See [`docs/architecture.md`](../docs/architecture.md) for what's live
instead, and why this was set aside.

- `story_simulator/`: `spatial.py`, `specialists.py`, `agents.py`,
  `game_config.py`, and the `npc`/`terrain`/`physics` agent configs.
- `tests/`: the tests for the above, plus the character-branch/module-toggle
  tests that no longer apply now that `_run_event_loop` only has one path.
