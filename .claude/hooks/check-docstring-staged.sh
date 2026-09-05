#!/bin/bash
# PreToolUse(git commit) check: catches a docstring edit before it's
# committed, at the moment content is staged. Complements
# stop-docstring-check.sh rather than replacing it: that Stop-hook
# version inspects `git diff HEAD` (still-uncommitted tracked changes)
# plus untracked files, which goes silently blind once a turn's changes
# are already committed by the time Stop fires -- a real gap under a
# commit-immediately workflow. Checking `git diff --cached` here instead
# means the signal can't be erased by the commit that's about to happen,
# since the commit itself is the trigger.
set -euo pipefail

input=$(cat)

if [[ -n "${STORY_SIM_HEADLESS_TEST:-}" ]]; then
  exit 0
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

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
  msg="This commit touches a docstring in the file(s) below. Before committing: review each for conciseness -- state the non-obvious WHY only (a hidden constraint, a subtle invariant, a workaround), not what the code does or its change/bug history; trim anything a future reader wouldn't miss:
${flagged}"
  jq -n --arg msg "$msg" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "allow", additionalContext: $msg}}'
fi

exit 0
