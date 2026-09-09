"""Confirms a native subagent's own turn detail is reachable from a HeadlessSession trace.

Originally a spike; kept as a live regression since
render_trace_follows_task_notification depends on this. Full finding:
docs/manifest/history.yaml:
project_history.native_subagent_detail_confirmed_reachable_via_task_notification_output_file
"""

import json
from pathlib import Path

import pytest

from emc2p.testing.headless_session import HeadlessSession

REPO_ROOT = Path(__file__).parent.parent


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

        # See history.yaml's own entry (module docstring) for what this confirms.
        assert sidechain_events, (
            "the subagent's own output_file exists but contains no "
            "isSidechain-tagged events -- capture_native_subagent_sidechain's "
            "premise does not hold for this CLI/version after all"
        )
        assert correlated, (
            "isSidechain events exist but none carry the agentId this "
            "notification named -- correlation would need a different field"
        )
