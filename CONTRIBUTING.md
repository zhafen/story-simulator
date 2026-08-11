# Contributing

story-simulator is a small, actively-changing project -- this is meant to
save you from having to reverse-engineer setup and conventions from
scratch, not a heavyweight process document.

## Dev setup

1. Clone with submodules (the registry engine, [`iacs`](iacs), is a git
   submodule):
   ```
   git clone --recurse-submodules <repo-url>
   # or, if already cloned:
   git submodule update --init --recursive
   ```
2. Install dependencies with [uv](https://docs.astral.sh/uv/):
   ```
   uv sync
   ```
3. Enable the repo's git hooks (checked into `.githooks/`, not the default
   `.git/hooks/`, so this is a one-time opt-in per clone):
   ```
   git config core.hooksPath .githooks
   ```
   The pre-commit hook runs `scripts/check-submodule-pointers.sh`, which
   catches an `iacs` pointer bump that's actually a rewind, or one that
   points at a commit only present locally -- see that script's own
   comments for the PR it was written in response to.
4. Have a Postgres instance reachable -- see the README's Quick start for
   the default DSN and how to point elsewhere with
   `STORY_SIM_DATABASE_DSN`.
5. Copy `.env.example` to `.env` if you need any of the variables it
   documents (most local dev doesn't).

## Running tests

```
uv run pytest
```

runs the full suite. `-m "not live"` (what CI runs) skips tests marked
`live`, which call a real Anthropic API and cost money -- only relevant to
code under `shelved/`, which isn't collected by default (see
`pyproject.toml`'s `testpaths`).

## Branch / PR conventions

- Branch off `main`, open a PR back into it. The PR template pre-fills the
  sections reviewers will look for (summary, key changes, test plan).
- CI (`.github/workflows/ci.yml`) runs the test suite against a real
  Postgres service container, plus the submodule-pointer check on every
  PR -- both need to pass before merging.
- If a PR touches `iacs`, double-check the submodule pointer is actually
  moving forward (an ancestor of the old commit is a rewind, not an
  update) and that the target commit is pushed to `iacs`'s own remote --
  the pre-commit hook and CI both check this, but it's easy to trip if
  you're working across both repos at once.
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
