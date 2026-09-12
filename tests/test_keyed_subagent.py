"""Tests for story_simulator.keyed_subagent.call_keyed_subagent's own
plumbing -- no live model call: run_tool_calling_loop itself is
monkeypatched, since these are mechanical argument-threading checks, not
a test of any model's actual judgment (see tests/test_resolve.py for
callers of call_keyed_subagent, which mock it at that boundary instead).
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from story_simulator import core
from story_simulator.keyed_subagent import call_keyed_subagent


def _open_session(tmp_path, client_trace_path=None):
    """A session with a real world open via core.start_world (the same
    Postgres bootstrap/schema setup a real client's start_world call
    goes through) -- call_keyed_subagent's own dispatch reads/writes
    through core.registrar_sessions, so it needs one open."""
    session = MagicMock()
    core.start_world(session, str(tmp_path / "save"), client_trace_path=client_trace_path)
    return session


class TestTracePathPlumbing:
    pytestmark = pytest.mark.slow

    """single_shared_trace_file: call_keyed_subagent forwards whatever
    trace_path the connected client recorded via start_world's own
    client_trace_path, so its own judgment call lands in that same file.
    """

    def test_passes_the_sessions_recorded_trace_path_through(self, monkeypatch, tmp_path):
        trace_path = tmp_path / "session_trace.jsonl"
        session = _open_session(tmp_path, client_trace_path=str(trace_path))

        captured = {}

        async def fake_run_tool_calling_loop(
            prompt, *, model, dispatch, tools, usage_log_path, trace_path, trace_actor, trace_origin
        ):
            captured["trace_path"] = trace_path
            captured["trace_actor"] = trace_actor
            captured["trace_origin"] = trace_origin
            return "answered"

        monkeypatch.setattr(
            "story_simulator.keyed_subagent.run_tool_calling_loop", fake_run_tool_calling_loop
        )

        result = asyncio.run(call_keyed_subagent("what happened?", session, origin="resolve_event"))

        assert result == "answered"
        assert captured["trace_path"] == trace_path
        assert captured["trace_actor"] == "keyed_subagent"
        assert captured["trace_origin"] == "resolve_event"

    def test_passes_none_when_no_client_trace_path_was_ever_recorded(self, monkeypatch, tmp_path):
        session = _open_session(tmp_path)  # no client_trace_path given

        captured = {}

        async def fake_run_tool_calling_loop(
            prompt, *, model, dispatch, tools, usage_log_path, trace_path, trace_actor, trace_origin
        ):
            captured["trace_path"] = trace_path
            return "answered"

        monkeypatch.setattr(
            "story_simulator.keyed_subagent.run_tool_calling_loop", fake_run_tool_calling_loop
        )

        asyncio.run(call_keyed_subagent("what happened?", session))

        assert captured["trace_path"] is None

    def test_omitted_origin_passes_none_not_an_empty_string(self, monkeypatch, tmp_path):
        """`origin` defaults to "" (matching JudgmentRequest's own
        default), but the trace writer's own convention for "not given"
        is None, not an empty string -- see run_tool_calling_loop's
        trace_origin (omits the key entirely only for None)."""
        session = _open_session(tmp_path)
        captured = {}

        async def fake_run_tool_calling_loop(
            prompt, *, model, dispatch, tools, usage_log_path, trace_path, trace_actor, trace_origin
        ):
            captured["trace_origin"] = trace_origin
            return "answered"

        monkeypatch.setattr(
            "story_simulator.keyed_subagent.run_tool_calling_loop", fake_run_tool_calling_loop
        )

        asyncio.run(call_keyed_subagent("what happened?", session))

        assert captured["trace_origin"] is None
