#!/bin/bash
# Nudges a Claude Code session to review its own docstring edits for
# conciseness before ending a turn -- see PR#96 review comment 11.
set -euo pipefail

input=$(cat)

# HeadlessSession's own `claude -p` subprocess has no user to defer to,
# so it must opt out of this nudge via an env var it sets on itself.
if [[ -n "${STORY_SIM_HEADLESS_TEST:-}" ]]; then
  exit 0
fi

# Recursion prevention: only nudge once per Stop attempt, mirroring
# stop-hook-git-check.sh.
stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active')
if [[ "$stop_hook_active" = "true" ]]; then
  exit 0
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

flagged=""

# Tracked files with uncommitted changes touching a `"""` line -- a
# proxy for "a docstring was added, removed, or had its edges edited".
while IFS= read -r f; do
  [[ -z "$f" || ! -f "$f" ]] && continue
  if git diff HEAD -- "$f" | grep -qE '^[+-].*"""'; then
    flagged+="$f"$'\n'
  fi
done < <(git diff --name-only HEAD -- '*.py' 2>/dev/null || true)

# Brand new, not-yet-tracked files: any `"""` anywhere counts, since the
# whole file is "changed".
while IFS= read -r f; do
  [[ -z "$f" || ! -f "$f" ]] && continue
  if grep -qE '"""' "$f"; then
    flagged+="$f"$'\n'
  fi
done < <(git ls-files --others --exclude-standard -- '*.py' 2>/dev/null || true)

if [[ -n "$flagged" ]]; then
  echo "This turn's diff touches a docstring in the file(s) below. Before stopping, review each for conciseness -- state the non-obvious WHY only (a hidden constraint, a subtle invariant, a workaround), not what the code does or its change/bug history; trim anything a future reader wouldn't miss:" >&2
  printf '%s' "$flagged" >&2
  exit 2
fi

exit 0
