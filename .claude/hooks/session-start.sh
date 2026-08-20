#!/bin/bash
set -euo pipefail

# .git/config is per-clone and doesn't survive a fresh container -- point
# git at the repo-tracked hooks dir on every boot so .githooks/pre-commit runs.
git config core.hooksPath .githooks

# .claude/settings.local.json (gitignored) never survives a fresh container,
# so re-apply the MCP allow rules to user-level settings on every boot.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

tmp=$(mktemp)
jq '.permissions.allow = ((.permissions.allow // []) + ["mcp__iacs__*", "mcp__story-simulator__*"] | unique)' "$SETTINGS" > "$tmp"
mv "$tmp" "$SETTINGS"
