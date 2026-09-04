"""Tests for story_simulator.resolve's responder dispatch, including
the "keyed_subagent" responder (see resolve.py's module docstring).

No live model calls: `call_keyed_subagent` is monkeypatched, since
these are mechanical dispatch/replay-bookkeeping checks, not a test of
DeepSeek (or any model)'s actual judgment quality -- see
tests/location_write_harness.py for that kind of comparison. The
tool-calling loop itself (`emc2p.agents.tool_calling_loop.run_tool_calling_loop`)
has its own tests in the emc2p repo.
"""

import asyncio
import time

import pytest

from story_simulator.resolve import JudgmentRequest, NeedsExternalInput, TurnReplay


def test_host_raises_needs_external_input():
    replay = TurnReplay(answers=[])
    with pytest.raises(NeedsExternalInput) as exc_info:
        asyncio.run(
            replay.resolve(JudgmentRequest(prompt="what happened?"), responder="host")
        )
    assert exc_info.value.responder == "host"


def test_keyed_subagent_answers_inline_without_raising(monkeypatch):
    async def fake_call_keyed_subagent(prompt: str, session) -> str:
        assert "what happened?" in prompt
        assert session == "sess-1"
        return "the car parked."

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[])
    result = asyncio.run(
        replay.resolve(
            JudgmentRequest(prompt="what happened?"), responder="keyed_subagent", session="sess-1"
        )
    )
    assert result == "the car parked."


def test_keyed_subagent_answer_is_cached_into_replay_answers(monkeypatch):
    """A later judgment call in the same turn pausing (e.g.
    responder="host") must not lose an earlier keyed_subagent answer.

    See TurnReplay.resolve's own comment and core._wrap_loop_result's
    `_encode_token(alias, replay.answers)`.
    """
    async def fake_call_keyed_subagent(prompt: str, session) -> str:
        return "resolved via deepseek"

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[])
    first = asyncio.run(
        replay.resolve(
            JudgmentRequest(prompt="first question"), responder="keyed_subagent", session="sess-1"
        )
    )
    assert first == "resolved via deepseek"
    assert replay.answers == ["resolved via deepseek"]

    with pytest.raises(NeedsExternalInput):
        asyncio.run(replay.resolve(JudgmentRequest(prompt="second question"), responder="host"))
    # The paused call's own answer isn't appended (that only happens on
    # resume) -- but the earlier keyed_subagent answer must still be in replay.answers.
    assert replay.answers == ["resolved via deepseek"]


def test_keyed_subagent_checks_in_once_deadline_passes(monkeypatch):
    """See TurnReplay.deadline / resolve()'s keyed_subagent branch: past
    the time budget, keyed_subagent must check in with the host instead.

    Instead of placing another (possibly slow) model call: with no
    budget at all, one advance_simulation call can chain many DeepSeek
    round-trips and blow past Claude Code's own ~60s MCP tool-call
    timeout.
    """
    called = False

    async def fake_call_keyed_subagent(prompt: str, session) -> str:
        nonlocal called
        called = True
        return "should not be reached"

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[], deadline=time.monotonic() - 1)  # already expired
    with pytest.raises(NeedsExternalInput) as exc_info:
        asyncio.run(
            replay.resolve(
                JudgmentRequest(prompt="what happened?"), responder="keyed_subagent", session="sess-1"
            )
        )
    assert exc_info.value.responder == "host"
    assert exc_info.value.is_checkpoint is True
    assert not called
    # This call_index's own answer must be left unrecorded so a resume
    # re-asks it fresh (with a new budget), not from a cached non-answer.
    assert replay.answers == []
    # Nor should the pause have consumed a call_index slot -- see
    # test_checkpoint_pause_leaves_call_index_untouched_for_resume below.
    assert replay.call_index == 0


def test_checkpoint_pause_leaves_call_index_untouched_for_resume(monkeypatch):
    """Regression for the bug this module's `is_checkpoint` plumbing fixes.

    Before the fix, a deadline check-in consumed the same `call_index`
    slot as the judgment call it interrupted; resuming then fed the
    host's "continue" reply into that call as if it were the real
    answer, so keyed_subagent was never actually asked again -- silently
    corrupting that event's resolution and leaving it eligible to be
    popped and re-paused forever (see story-simulator#70's investigation).

    Simulates one resume cycle directly against `TurnReplay`, without
    `core.py`'s token plumbing: a fresh (unexpired) deadline after the
    pause must let the SAME call actually reach keyed_subagent, not
    short-circuit to a cached non-answer.
    """
    calls = []

    async def fake_call_keyed_subagent(prompt: str, session) -> str:
        calls.append(prompt)
        return "car_c parked in parking_spot_2."

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[], deadline=time.monotonic() - 1)  # already expired
    with pytest.raises(NeedsExternalInput) as exc_info:
        asyncio.run(
            replay.resolve(
                JudgmentRequest(prompt="resolve car_c_park"), responder="keyed_subagent", session="sess-1"
            )
        )
    assert exc_info.value.is_checkpoint is True
    assert replay.answers == []
    assert replay.call_index == 0

    # Resuming (per core._resolve_args's is_checkpoint branch) discards the
    # check-in's own "continue" reply rather than appending it -- simulated
    # here by just giving the same replay object a fresh budget, exactly as
    # core._run_event_loop does on every call, resumed or not.
    replay.deadline = time.monotonic() + 30
    result = asyncio.run(
        replay.resolve(
            JudgmentRequest(prompt="resolve car_c_park"), responder="keyed_subagent", session="sess-1"
        )
    )
    assert result == "car_c parked in parking_spot_2."
    assert len(calls) == 1 and "resolve car_c_park" in calls[0]  # really asked, not skipped
    assert replay.answers == ["car_c parked in parking_spot_2."]


def test_keyed_subagent_within_budget_still_answers_inline(monkeypatch):
    """The counterpart to the expired-deadline test: a deadline that
    hasn't passed yet must not block the ordinary inline-answer path."""
    async def fake_call_keyed_subagent(prompt: str, session) -> str:
        return "the car parked."

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[], deadline=time.monotonic() + 30)
    result = asyncio.run(
        replay.resolve(
            JudgmentRequest(prompt="what happened?"), responder="keyed_subagent", session="sess-1"
        )
    )
    assert result == "the car parked."
    assert replay.answers == ["the car parked."]


def test_resolve_args_discards_checkpoint_answer_instead_of_banking_it():
    """`core._resolve_args`'s own half of the `is_checkpoint` fix: resuming
    a checkpoint pause must not fold the host's "continue" reply into the
    answer bank `TurnReplay` replays from -- see
    `test_checkpoint_pause_leaves_call_index_untouched_for_resume` above
    for `TurnReplay`'s own half.
    """
    from story_simulator.core import _encode_token, _resolve_args

    # A checkpoint pause's own token: whatever was already genuinely
    # answered, unchanged -- the paused call itself never got an answer.
    token = _encode_token("car_c_park", ["earlier real answer"], is_checkpoint=True)

    alias, replay = _resolve_args(token, "Continue the simulation.")
    assert alias == "car_c_park"
    # The check-in reply ("Continue the simulation.") must NOT appear here --
    # only the genuine prior answer survives the resume.
    assert replay.answers == ["earlier real answer"]


def test_resolve_args_banks_an_ordinary_pauses_answer_normally():
    """The non-checkpoint case is unchanged: an ordinary host/subagent/human
    pause's answer is real content and belongs in the bank."""
    from story_simulator.core import _encode_token, _resolve_args

    token = _encode_token("car_c_park", ["earlier real answer"])  # is_checkpoint defaults False
    alias, replay = _resolve_args(token, "car_c parked in parking_spot_2.")
    assert alias == "car_c_park"
    assert replay.answers == ["earlier real answer", "car_c parked in parking_spot_2."]


def test_unknown_responder_raises_value_error():
    replay = TurnReplay(answers=[])
    with pytest.raises(ValueError):
        asyncio.run(
            replay.resolve(JudgmentRequest(prompt="?"), responder="not_a_real_responder")
        )
