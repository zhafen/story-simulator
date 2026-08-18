"""Unit tests for HeadlessSession's timeout/kill mechanics -- turn_timeout,
session_timeout, and _fail's process-termination path. No real `claude`
CLI or Anthropic API calls: a plain `cat` subprocess stands in for the
real one, so these run fast and free as part of the normal (non-live)
suite rather than needing @pytest.mark.live.
"""

import subprocess
import time

import pytest

from tests.test_human_validated import HeadlessSession


def _stub_session(tmp_path, **kwargs) -> HeadlessSession:
    """A HeadlessSession with `cat` standing in for the real `claude -p`
    subprocess: reads stdin until EOF then exits promptly, unlike a bare
    `sleep`, which would ignore stdin closing and force close()'s full
    30s wait/kill fallback on every test here. Bypasses __enter__
    entirely (no shutil.which("claude") check, no real MCP config) since
    only the timeout/kill mechanics are under test, not an actual
    conversation.
    """
    session = HeadlessSession(tmp_path / "save", **kwargs)
    session.trace_path = tmp_path / "trace.jsonl"
    session._session_deadline = time.monotonic() + session.session_timeout
    session._trace_file = open(session.trace_path, "w")
    session.proc = subprocess.Popen(
        ["cat"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    return session


def test_fail_terminates_a_still_running_process_without_hanging(tmp_path):
    """The bug this guards against: _fail() used to read the process's
    stderr (blocking until EOF) before ever killing it -- a deadlock,
    since EOF only arrives once the process exits, and nothing killed it
    until after that read. Confirmed live: every timeout in this harness
    silently hung instead of firing until this was fixed."""
    session = _stub_session(tmp_path)
    proc = session.proc
    assert proc.poll() is None  # still running

    start = time.monotonic()
    with pytest.raises(pytest.fail.Exception) as exc_info:
        session._fail("boom")
    elapsed = time.monotonic() - start

    assert "boom" in str(exc_info.value)
    assert elapsed < 10, f"_fail took {elapsed:.1f}s -- should return quickly, not hang"
    assert proc.poll() is not None, "the subprocess must be terminated, not left running"


def test_turn_timeout_fires_with_its_own_message(tmp_path):
    session = _stub_session(tmp_path, turn_timeout=0.2, session_timeout=300)
    start = time.monotonic()
    with pytest.raises(pytest.fail.Exception) as exc_info:
        session.send_turn("hello")
    elapsed = time.monotonic() - start

    assert "turn timed out after 0.2s" in str(exc_info.value)
    assert elapsed < 10


def test_session_timeout_fires_when_it_is_the_sooner_deadline(tmp_path):
    """send_turn's deadline is min(turn_deadline, session_deadline) -- a
    session past its own overall budget must fail with the session
    message, not silently wait out the (deliberately generous)
    turn_timeout instead."""
    session = _stub_session(tmp_path, turn_timeout=300, session_timeout=300)
    session._session_deadline = time.monotonic() - 1  # already past
    start = time.monotonic()
    with pytest.raises(pytest.fail.Exception) as exc_info:
        session.send_turn("hello")
    elapsed = time.monotonic() - start

    assert "session timed out after 300s" in str(exc_info.value)
    assert elapsed < 10


def test_close_is_safe_to_call_twice(tmp_path):
    session = _stub_session(tmp_path)
    session.close()
    session.close()  # must not raise
    assert session.proc is None
