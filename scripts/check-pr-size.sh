#!/usr/bin/env bash
# git hook (pre-commit and pre-push): warn -- non-blocking -- when the
# branch's diff vs its base crosses a size threshold, prompting a check
# on whether the remaining work still belongs in this PR. Lives here
# (agent-independent) rather than in .claude/hooks/ so it runs for any
# commit/push regardless of what made it, not just a Claude Code session.
set -euo pipefail

MAX_LINES=400
MAX_FILES=15

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

base=""
for ref in origin/main origin/master; do
  if git rev-parse --verify -q "$ref" >/dev/null 2>&1; then
    candidate=$(git merge-base HEAD "$ref" 2>/dev/null) || continue
    if [[ -n "$candidate" ]]; then
      base="$candidate"
      break
    fi
  fi
done
[[ -z "$base" ]] && exit 0

# files/added/deleted for a diff range or pathspec, numstat-based so a
# file with zero insertions or zero deletions still counts correctly
# (--shortstat drops whichever side is zero, which shortstat parsing
# would otherwise silently miscount).
numstat_total() {
  git diff --numstat "$@" -- . 2>/dev/null | awk '
    { files++; add += ($1 == "-" ? 0 : $1); del += ($2 == "-" ? 0 : $2) }
    END { printf "%d %d %d", files + 0, add + 0, del + 0 }
  '
}

read -r committed_files committed_add committed_del <<<"$(numstat_total "$base"...HEAD)"
read -r staged_files staged_add staged_del <<<"$(numstat_total --cached)"

# Approximate, not exact: a file touched both earlier on the branch and
# in the currently staged change is counted twice. Good enough for a
# nudge, not meant as a precise metric.
total_files=$((committed_files + staged_files))
total_lines=$((committed_add + committed_del + staged_add + staged_del))

if (( total_files > MAX_FILES || total_lines > MAX_LINES )); then
  echo "This branch's diff vs ${base} is now ~${total_lines} lines across ${total_files} files (threshold: ${MAX_LINES} lines / ${MAX_FILES} files). Before continuing: does everything in this diff still belong in one PR, or should the next chunk of work move to its own branch/PR?" >&2
fi

exit 0
