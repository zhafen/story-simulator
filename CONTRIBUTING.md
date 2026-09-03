# Contributing

story-simulator is a small, actively-changing project -- this is meant to
save you from having to reverse-engineer setup and conventions from
scratch, not a heavyweight process document.

## Dev setup

1. Clone normally -- no submodules. The registry engine, [`emc2p`](https://github.com/zhafen/emc2p),
   is a plain pinned dependency (`[tool.uv.sources]` in `pyproject.toml`),
   not vendored in this repo's own tree.
2. Install dependencies with [uv](https://docs.astral.sh/uv/):
   ```
   uv sync
   ```
3. Have a Postgres instance reachable -- see the README's Quick start for
   the default DSN and how to point elsewhere with
   `STORY_SIM_DATABASE_DSN`.
4. Copy `.env.example` to `.env` if you need any of the variables it
   documents (most local dev doesn't).

If you're actively co-developing emc2p alongside this repo, a local,
gitignored `uv.toml` (not `pyproject.toml`) can override the pinned
dependency to a local editable path for faster iteration, e.g.:
```toml
[tool.uv.sources]
emc2p = { path = "../emc2p", editable = true }
```
The committed dependency in `pyproject.toml` stays the pinned git
revision everyone else (and CI) installs.

## Running tests

```
uv run pytest
```

runs the full suite. `-m "not live"` (what CI runs) skips tests marked
`live`, which call a real Anthropic API and cost money -- only relevant to
code under `shelved/`, which isn't collected by default (see
`pyproject.toml`'s `testpaths`).

## Code style

### Comments and docstrings

- A docstring (module/class/function) opens with a summary of 2 lines or
  less, then a blank line, then as much further detail as needed.
- A comment block sitting as the first statement of a function body
  becomes a docstring instead, formatted the same way.
- Any other comment block (a module-level constant, a note mid-function)
  is capped at a 2-line summary -- no continuation paragraph.
- Already-compliant comments/docstrings don't need reformatting just to
  match this convention.

## Branch / PR conventions

- Branch off `main`, open a PR back into it. The PR template pre-fills the
  sections reviewers will look for (summary, key changes, test plan).
- CI (`.github/workflows/ci.yml`) runs the test suite against a real
  Postgres service container -- needs to pass before merging.
- If a PR bumps the pinned `emc2p` revision (`[tool.uv.sources]` in
  `pyproject.toml`), double-check the target commit is actually pushed to
  `emc2p`'s own remote and moving forward, not a rewind -- `uv lock` will
  fail outright if the commit isn't reachable, but it won't catch a
  rewind on its own.
- See [`docs/architecture.md`](docs/architecture.md) for how the pieces
  fit together, and [`CLAUDE.md`](CLAUDE.md) for conventions specific to
  AI-assisted sessions working in this repo (branch/session-recovery
  behavior, the narrator-prefix convention, etc.) -- most of it is useful
  background for a human contributor too.
- Larger changes: check [the v1.0 roadmap tracking issue](https://github.com/zhafen/story-simulator/issues/45)
  first. It's the live source of truth for what's planned and in what
  order. New requirements are tracked as GitHub issues, not
  `docs/manifest/story-simulator.yaml` -- see
  [#47](https://github.com/zhafen/story-simulator/issues/47) for what's
  happening to what's already recorded there.
