#!/usr/bin/env bash
# git pre-commit hook: flags a docstring edit in staged Python files at
# the moment content is staged, so the signal can't be erased by the
# commit that's about to happen -- the commit itself is the trigger.
# Replaces two earlier .claude-only hooks: a Stop-hook version that
# inspected git diff HEAD at turn-end (blind once a turn's edits were
# already committed) and a PreToolUse version scoped to Claude Code
# sessions only. Living here instead makes it apply to any commit.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

flagged=""
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if git diff --cached -- "$f" | grep -qE '^[+-].*"""'; then
    flagged+="$f"$'\n'
  fi
done < <(git diff --cached --name-only -- '*.py' 2>/dev/null || true)

if [[ -n "$flagged" ]]; then
  echo "This commit touches a docstring in the file(s) below. Before committing: review each for conciseness -- state the non-obvious WHY only (a hidden constraint, a subtle invariant, a workaround), not what the code does or its change/bug history; trim anything a future reader wouldn't miss:" >&2
  printf '%s' "$flagged" >&2
fi

exit 0
