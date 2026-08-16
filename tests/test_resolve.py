"""Tests for story_simulator.resolve's responder dispatch, including the
"keyed_subagent" responder (see resolve.py's module docstring). No live
model calls: `call_keyed_subagent` is monkeypatched, since these are
mechanical dispatch/replay-bookkeeping checks, not a test of DeepSeek (or
any model)'s actual judgment quality -- see tests/location_write_harness.py
for that kind of comparison.
"""

import asyncio

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
    async def fake_call_keyed_subagent(prompt: str) -> str:
        assert "what happened?" in prompt
        return "the car parked."

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[])
    result = asyncio.run(
        replay.resolve(JudgmentRequest(prompt="what happened?"), responder="keyed_subagent")
    )
    assert result == "the car parked."


def test_keyed_subagent_answer_is_cached_into_replay_answers(monkeypatch):
    """A later judgment call in the same turn pausing (e.g. responder="host")
    must not lose an earlier keyed_subagent answer on resume -- see
    TurnReplay.resolve's own comment and core._wrap_loop_result's
    `_encode_token(alias, replay.answers)`."""
    async def fake_call_keyed_subagent(prompt: str) -> str:
        return "resolved via deepseek"

    monkeypatch.setattr(
        "story_simulator.keyed_subagent.call_keyed_subagent", fake_call_keyed_subagent
    )

    replay = TurnReplay(answers=[])
    first = asyncio.run(
        replay.resolve(JudgmentRequest(prompt="first question"), responder="keyed_subagent")
    )
    assert first == "resolved via deepseek"
    assert replay.answers == ["resolved via deepseek"]

    with pytest.raises(NeedsExternalInput):
        asyncio.run(replay.resolve(JudgmentRequest(prompt="second question"), responder="host"))
    # The paused call's own answer isn't appended (that only happens on
    # resume, via _resolve_args) -- but the earlier keyed_subagent answer
    # must still be sitting in replay.answers at this point, ready to be
    # encoded into the resume token.
    assert replay.answers == ["resolved via deepseek"]


def test_unknown_responder_raises_value_error():
    replay = TurnReplay(answers=[])
    with pytest.raises(ValueError):
        asyncio.run(
            replay.resolve(JudgmentRequest(prompt="?"), responder="not_a_real_responder")
        )
