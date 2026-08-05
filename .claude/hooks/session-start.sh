#!/bin/bash
set -euo pipefail

# .git/config is per-clone and, like .claude/settings.local.json below,
# doesn't survive a fresh container - point git at the repo-tracked hooks
# dir on every boot so .githooks/pre-commit (submodule pointer checks)
# actually runs. Cheap and idempotent, so do this unconditionally rather
# than only in remote sessions.
git config core.hooksPath .githooks

# Claude Code on the web spins up a fresh, ephemeral container per session, so
# .claude/settings.local.json (gitignored, user-owned) never survives between
# sessions, and the repo-committed .claude/settings.json permissions rely on a
# project-trust step that a fresh container never gets to accept. User-level
# settings (~/.claude/settings.json) aren't gated by repo trust, so re-apply
# the MCP allow rules there on every boot.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

tmp=$(mktemp)
jq '.permissions.allow = ((.permissions.allow // []) + ["mcp__iacs__*", "mcp__story-simulator__*"] | unique)' "$SETTINGS" > "$tmp"
mv "$tmp" "$SETTINGS"
