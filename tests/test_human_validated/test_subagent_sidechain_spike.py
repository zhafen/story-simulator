"""Spike: does the connected "claude" CLI's own subagent mechanism ever
expose the subagent's internal turns anywhere reachable from a
HeadlessSession trace?

This answers mrtr_subagent_trace's capture_native_subagent_sidechain
open question -- see the requirement-tree manifest. Not a regression
gate on story-simulator's own behavior: doesn't touch start_world or any
MCP tool, just a HeadlessSession talking to the "claude" CLI directly
with strict_tool_isolation=False so its subagent mechanism stays
available.

FINDING (first run, this environment's claude CLI, version 2.1.263):
the manifest's original guess -- an inline isSidechain/parentToolUseId
event interleaved into the *parent's own* stream-json -- was wrong in
its specifics but right in substance. What actually happens:

- The parent's own trace_path never gets subagent tool_use/tool_result
  detail inline. It only ever sees a `system`/`task_notification` event
  once the subagent finishes, carrying `tool_use_id` (correlating back
  to the spawning tool_use, e.g. an "Agent" tool_use -- not literally
  named "Task" in this CLI version), a one-line `summary`, and an
  `output_file` path.
- That `output_file` is a SEPARATE .jsonl-per-line file (not the
  parent's trace_path) holding the subagent's own full turn-by-turn
  detail, and its events ARE tagged `isSidechain: true` plus an
  `agentId` matching the notification's own `task_id` -- confirming the
  manifest's core premise (the CLI already emits sidechain-tagged
  subagent detail) while correcting *where* it lives.

So this is structurally identical to nested_subtrace_structure/
render_trace_gains_subtrace_rendering's own proposed shape (a separate
file + a correlation id + join-at-parse-time) -- except the CLI already
produces that separate file for free; nothing needs to write it.
render_trace would only need to (a) recognize a task_notification event,
(b) parse its output_file's own isSidechain-tagged JSONL, (c) attach the
result under the tool_use_id it names.

Caveat: this ran against whatever "claude" binary happens to be on PATH
in this sandboxed CI/session environment, which already exhibits
Cowork/task-list-specific tool naming (TaskCreate/TaskGet as a todo
list, "Agent" for subagent spawn) rather than the plain terminal Claude
Code product's classic "Task" tool name. A real player's own local
Claude Code install may differ -- worth re-running this spike against
that surface before fully committing to this shape.

A single run, not a live_trial repeat -- this is a yes/no spike on the
CLI's own trace format, not a flaky game-logic assertion that benefits
from multiple trials.
"""

import json
from pathlib import Path

import pytest

from emc2p.testing.headless_session import HeadlessSession

REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.live
def test_subagent_turns_reachable_via_task_notification_output_file(tmp_path: Path):
    with HeadlessSession(
        mcp_config=REPO_ROOT / ".mcp.json",
        allowed_tools=["Task"],
        cwd=REPO_ROOT,
        model="claude-haiku-4-5-20251001",
        strict_tool_isolation=False,  # leave the subagent mechanism available
        trace_dir=tmp_path,
    ) as session:
        result = session.send_turn(
            "Launch a subagent (background agent/task) that computes 17 * 23 "
            "and reports back only the final number. Do not compute it "
            "yourself -- delegate it. Once the subagent replies, tell me "
            "its answer and nothing else."
        )
        print(f"result: {result!r}")
        print(f"trace: {session.trace_path}")

        raw_lines = session.trace_path.read_text().splitlines()
        events = []
        for line in raw_lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        notifications = [
            e
            for e in events
            if e.get("type") == "system"
            and e.get("subtype") == "task_notification"
            and e.get("output_file")
        ]

        print(f"{len(events)} total stream-json events in the parent's own trace_path")
        print(f"{len(notifications)} task_notification events carrying an output_file")

        assert notifications, (
            "no subagent was ever spawned (or none reported an output_file) -- "
            "inconclusive, not evidence against sidechain visibility"
        )

        output_path = Path(notifications[0]["output_file"])
        assert output_path.exists(), f"output_file {output_path} does not exist on disk"

        subagent_lines = output_path.read_text().splitlines()
        subagent_events = [json.loads(line) for line in subagent_lines if line.strip()]
        sidechain_events = [e for e in subagent_events if e.get("isSidechain")]
        correlated = [
            e for e in subagent_events if e.get("agentId") == notifications[0]["task_id"]
        ]

        print(f"{len(subagent_events)} events in the subagent's own output_file")
        print(f"{len(sidechain_events)} isSidechain-tagged events in it")
        print(f"{len(correlated)} events tagged with the notification's own task_id")

        # The actual finding this spike exists to establish: the subagent's
        # own turn detail is reachable (a separate file, pointed to by the
        # parent trace's task_notification event) and self-identifies as
        # sidechain content correlated back to the spawning tool_use --
        # confirming capture_native_subagent_sidechain's premise, with the
        # correction that it's a separate file, not an inline event.
        assert sidechain_events, (
            "the subagent's own output_file exists but contains no "
            "isSidechain-tagged events -- capture_native_subagent_sidechain's "
            "premise does not hold for this CLI/version after all"
        )
        assert correlated, (
            "isSidechain events exist but none carry the agentId this "
            "notification named -- correlation would need a different field"
        )
