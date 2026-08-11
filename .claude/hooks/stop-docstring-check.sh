#!/bin/bash
# Nudges a Claude Code session to review its own docstring edits for
# conciseness before ending a turn -- see PR#96 review comment 11
# (docstrings had grown to ~30-line rationale/history essays). Judging
# "concise" isn't something a shell script can do; this only does the
# cheap, deterministic part -- detect that a docstring-shaped region was
# touched -- and hands the actual review back to the model already in the
# loop for this session, the same way stop-hook-git-check.sh's plain-text
# feedback loops a git-state finding back to the model rather than trying
# to fix it in bash.
set -euo pipefail

input=$(cat)

# Recursion prevention: only nudge once per Stop attempt, mirroring
# stop-hook-git-check.sh -- if the model's forced follow-up turn doesn't
# resolve it, don't loop forever re-flagging the same diff.
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

# Tracked files with uncommitted changes (staged and/or unstaged) touching
# a `"""` line -- a very likely proxy for "a docstring was added, removed,
# or had its opening/closing line edited". Doesn't catch an edit confined
# entirely to a docstring's interior lines with no `"""` in the diff, but a
# false negative there just means one less nudge, not a wrong one.
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
