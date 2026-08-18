#!/usr/bin/env python3
"""Extract Claude Code account usage percentages via a real interactive session.

`claude -p`/`--output-format stream-json` cannot answer this: `/usage` is a
TUI-only slash command and renders nothing over the print-mode stream
(confirmed: 0 turns, empty result). This drives an actual interactive
`claude` session over a pseudoterminal, walks it past whatever one-time
prompts appear (first-run onboarding, workspace trust, MCP-server-enable),
sends `/usage`, and parses the two numbers that matter for comparing usage
before/after a test batch: current-session % used and current-week % used.

This whole PTY-driving approach is a workaround for the lack of a direct,
scriptable way to read this data (a `claude usage`-style CLI flag or
non-interactive API, not `/usage`'s TUI-only rendering). If/when such a
feature ships, this script should be deprecated in favor of it -- the PTY
approach is inherently fragile (depends on `/usage`'s exact screen text
and this container's onboarding-prompt sequence, both of which can change
out from under it).

Onboarding wizard: this container's `~/.claude.json` has never been through
the interactive TUI, so `theme`/`hasCompletedOnboarding` are unset and a
fresh interactive launch shows a theme picker followed by a login-method
screen that would start a *real* browser OAuth flow (the headless
credential used by `claude -p`/`claude auth status` isn't picked up by that
wizard). This script temporarily sets those two fields so onboarding is
skipped, and always restores the original file afterward (even on
failure) -- never leaves the account config altered.

Workspace trust and the "N new MCP servers found" prompt don't persist
across runs that this script terminates non-gracefully (confirmed: still
false/empty in ~/.claude.json after a prior successful run), so every
invocation re-answers them; this is expected, not a bug.

Usage:
    python3 scripts/get_usage.py              # human-readable summary
    python3 scripts/get_usage.py --json        # machine-readable JSON
    python3 scripts/get_usage.py --raw         # also dump the raw captured screen
"""
from __future__ import annotations

import argparse
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_CONFIG_PATH = Path(os.environ.get("CLAUDE_CONFIG_PATH", Path.home() / ".claude.json"))

ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]")

_PCT_USED_RE = re.compile(r"(\d+)%\s*used", re.IGNORECASE)
_RESETS_RE = re.compile(r"Resets\s+(.*?\(UTC\))", re.IGNORECASE | re.DOTALL)
_PROMO_RE = re.compile(r"(\+\d+%\s*weekly limits promo[^\r\n]*?clau\.de\S*)", re.IGNORECASE)


class UsageExtractionError(RuntimeError):
    """Raised when the interactive session didn't reach a parseable /usage screen."""


def _read_available(fd: int, timeout: float = 1.0, idle_cutoff: float = 1.5) -> bytes:
    buf = b""
    last_data = time.monotonic()
    while True:
        remaining_budget = idle_cutoff
        r, _, _ = select.select([fd], [], [], timeout)
        if fd in r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            last_data = time.monotonic()
        else:
            if time.monotonic() - last_data > idle_cutoff:
                break
    return buf


def _plain(data: bytes) -> str:
    return ANSI_RE.sub(b"", data).decode(errors="replace")


def _parse_usage_screen(text: str) -> dict:
    """Pull the two headline percentages (+ reset times) out of the /usage screen's text.

    Newlines are largely gone by the time text reaches here (the TUI redraws
    with carriage returns, not linefeeds), so this slices on the section
    headers ("Current session" / "Current week") rather than matching
    line-by-line.
    """
    if "Current session" not in text or "Current week" not in text:
        raise UsageExtractionError(
            "captured screen doesn't contain the expected /usage sections -- "
            "see the raw capture for what actually rendered"
        )

    session_block = text.split("Current session", 1)[1].split("Current week", 1)[0]
    week_block = text.split("Current week", 1)[1]

    session_pct_m = _PCT_USED_RE.search(session_block)
    week_pct_m = _PCT_USED_RE.search(week_block)
    if not session_pct_m or not week_pct_m:
        raise UsageExtractionError("found the section headers but not a 'N% used' figure in one of them")

    session_reset_m = _RESETS_RE.search(session_block)
    week_reset_m = _RESETS_RE.search(week_block)
    promo_m = _PROMO_RE.search(week_block)

    return {
        "session_pct_used": int(session_pct_m.group(1)),
        "session_resets": session_reset_m.group(1).strip() if session_reset_m else None,
        "week_pct_used": int(week_pct_m.group(1)),
        "week_resets": week_reset_m.group(1).strip() if week_reset_m else None,
        "week_promo": promo_m.group(1).strip() if promo_m else None,
    }


class _OnboardingPatch:
    """Temporarily marks onboarding/theme as already-set in ~/.claude.json so
    an interactive launch skips straight past the theme-picker + login-method
    wizard (which would otherwise start a real browser OAuth flow), then
    restores the file exactly as it was found -- even if the caller raises.
    """

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._original_bytes: bytes | None = None

    def __enter__(self) -> "_OnboardingPatch":
        self._original_bytes = self.config_path.read_bytes()
        data = json.loads(self._original_bytes)
        data["theme"] = "dark"
        data["hasCompletedOnboarding"] = True
        self.config_path.write_text(json.dumps(data, indent=2))
        return self

    def __exit__(self, *exc_info) -> None:
        if self._original_bytes is not None:
            self.config_path.write_bytes(self._original_bytes)


def _drive_session(cwd: Path, startup_timeout: float, usage_timeout: float) -> tuple[dict, list[tuple[str, bytes]]]:
    master_fd, slave_fd = pty.openpty()
    env = {**os.environ, "TERM": "xterm-256color"}
    proc = subprocess.Popen(
        ["claude"],
        cwd=str(cwd),
        env=env,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    log: list[tuple[str, bytes]] = []

    def send(s: str) -> None:
        os.write(master_fd, s.encode())

    try:
        out = _read_available(master_fd, timeout=startup_timeout, idle_cutoff=2.0)
        log.append(("startup", out))
        plain = _plain(out).lower()

        if "choose the text style" in plain:
            send("\r")
            out = _read_available(master_fd, timeout=2.5, idle_cutoff=2.0)
            log.append(("after-theme-enter", out))
            plain = _plain(out).lower()

        if "select login method" in plain or "login method" in plain:
            raise UsageExtractionError(
                "onboarding still requested a login method -- the "
                "theme/hasCompletedOnboarding patch didn't take effect, and "
                "proceeding would start a real browser OAuth flow, so this "
                "aborted instead of guessing at it"
            )

        if "trust" in plain:
            send("\r")
            out = _read_available(master_fd, timeout=2.5, idle_cutoff=2.0)
            log.append(("after-trust-enter", out))
            plain = _plain(out).lower()

        if "mcp server" in plain:
            time.sleep(0.5)
            send("\r")
            out = _read_available(master_fd, timeout=2.5, idle_cutoff=2.0)
            log.append(("after-mcp-enter", out))

        time.sleep(1.5)
        send("/usage\r")
        out = _read_available(master_fd, timeout=usage_timeout, idle_cutoff=4.0)
        log.append(("after-usage", out))

        combined = "".join(_plain(chunk) for _, chunk in log)
        parsed = _parse_usage_screen(combined)
        return parsed, log
    finally:
        send("\x1b")  # Esc, in case the usage popup is still open
        time.sleep(0.2)
        send("\x03")
        time.sleep(0.2)
        send("\x03")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        os.close(master_fd)


def get_usage(
    cwd: Path = REPO_ROOT,
    *,
    config_path: Path = CLAUDE_CONFIG_PATH,
    startup_timeout: float = 3.0,
    usage_timeout: float = 6.0,
) -> dict:
    """Return {"session_pct_used", "session_resets", "week_pct_used", "week_resets", "week_promo"}.

    Raises UsageExtractionError if the interactive session never reached a
    parseable /usage screen (e.g. an unexpected prompt appeared).
    """
    if shutil.which("claude") is None:
        raise UsageExtractionError("claude CLI not on PATH")
    if not config_path.exists():
        raise UsageExtractionError(f"no Claude config found at {config_path}")

    with _OnboardingPatch(config_path):
        parsed, _log = _drive_session(cwd, startup_timeout, usage_timeout)
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", type=Path, default=REPO_ROOT, help="Directory to launch claude in (default: repo root)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a summary")
    parser.add_argument("--raw", action="store_true", help="Also print the raw captured terminal screens (for debugging)")
    args = parser.parse_args()

    try:
        if args.raw:
            with _OnboardingPatch(CLAUDE_CONFIG_PATH):
                parsed, log = _drive_session(args.cwd, startup_timeout=3.0, usage_timeout=6.0)
            for label, chunk in log:
                print(f"\n=== {label} ===", file=sys.stderr)
                print(_plain(chunk), file=sys.stderr)
        else:
            parsed = get_usage(cwd=args.cwd)
    except UsageExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        parsed["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        print(json.dumps(parsed, indent=2))
    else:
        print(f"Current session: {parsed['session_pct_used']}% used (resets {parsed['session_resets']})")
        print(f"Current week:    {parsed['week_pct_used']}% used (resets {parsed['week_resets']})")
        if parsed.get("week_promo"):
            print(parsed["week_promo"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
