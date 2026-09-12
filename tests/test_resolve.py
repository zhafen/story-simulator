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
    `_save_pending(registrar, alias, replay.answers)`.
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
    budget at all, one advance_simulation call could chain many DeepSeek
    round-trips with no visibility into what it's doing until it's done --
    see config.DEFAULT_KEYED_SUBAGENT_TIME_BUDGET_SECONDS's own comment
    for what actually bounds a single stdio MCP tool call.
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

    A deadline check-in used to consume the interrupted call's own
    `call_index` slot, so resuming fed the host's "continue" reply into
    it as if it were the real answer -- keyed_subagent was never asked
    again. Confirms a resume instead retries the same call fresh.
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

    # Resuming discards the check-in's reply (core._resolve_args);
    # simulated here via a fresh deadline, as every call gets on resume.
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


def _pending_registrar():
    """A fresh in-memory registrar with `pending_resolution`'s schema
    declared, matching real usage: `start_world` always loads
    manifest/builtins.yaml before any `_save_pending`/`_load_pending` call
    can happen. Without this, `is_checkpoint` (undeclared) would be typed
    from shorthand inference alone, which -- unlike the real declared
    `bool` field -- round-trips as the *string* "False"/"True", not a
    real boolean (Python's `bool("False")` is `True`).
    """
    from emc2p.registrar import Registrar
    from story_simulator.config import MANIFEST_DIR

    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)])
    return registrar


@pytest.mark.slow
def test_resolve_args_discards_checkpoint_answer_instead_of_banking_it():
    """`_resolve_args`'s half of the `is_checkpoint` fix: a checkpoint's
    "continue" reply must not enter `TurnReplay`'s answer bank.
    """
    from story_simulator.core import _resolve_args, _save_pending

    registrar = _pending_registrar()
    # A checkpoint pause's own saved state: whatever was already genuinely
    # answered, unchanged -- the paused call itself never got an answer.
    token = _save_pending(registrar, "car_c_park", ["earlier real answer"], is_checkpoint=True)

    alias, replay = _resolve_args(registrar, token, "Continue the simulation.")
    assert alias == "car_c_park"
    # The check-in reply ("Continue the simulation.") must NOT appear here --
    # only the genuine prior answer survives the resume.
    assert replay.answers == ["earlier real answer"]


@pytest.mark.slow
def test_resolve_args_banks_an_ordinary_pauses_answer_normally():
    """The non-checkpoint case is unchanged: an ordinary host/subagent/human
    pause's answer is real content and belongs in the bank."""
    from story_simulator.core import _resolve_args, _save_pending

    registrar = _pending_registrar()
    token = _save_pending(registrar, "car_c_park", ["earlier real answer"])  # is_checkpoint defaults False
    alias, replay = _resolve_args(registrar, token, "car_c parked in parking_spot_2.")
    assert alias == "car_c_park"
    assert replay.answers == ["earlier real answer", "car_c parked in parking_spot_2."]


@pytest.mark.slow
def test_save_pending_resume_token_is_just_the_alias():
    """Regression guard for issue #75's root cause: the resume_token must
    be a short, already-known-safe identifier, not an encoded blob the
    connected model has to relay back byte-for-byte -- see
    `_save_pending`'s own docstring.
    """
    from story_simulator.core import _save_pending

    registrar = _pending_registrar()
    token = _save_pending(registrar, "car_c_park", ["a long answer " * 200], is_checkpoint=False)
    assert token == "car_c_park"


@pytest.mark.slow
def test_load_pending_round_trips_answers_and_checkpoint_flag():
    from story_simulator.core import _load_pending, _save_pending

    registrar = _pending_registrar()
    _save_pending(registrar, "car_c_park", ["first", "second"], is_checkpoint=True)
    alias, answers, is_checkpoint = _load_pending(registrar, "car_c_park")
    assert alias == "car_c_park"
    assert answers == ["first", "second"]
    assert is_checkpoint is True


@pytest.mark.slow
def test_load_pending_raises_clear_error_for_unknown_alias():
    """No `pending_resolution` row for this alias (a tampered/invented
    resume_token, or one from a different world) must raise a clear,
    actionable error -- not a raw decode crash (see issue #75)."""
    from story_simulator.core import _load_pending

    registrar = _pending_registrar()
    with pytest.raises(ValueError, match="not_a_real_alias"):
        _load_pending(registrar, "not_a_real_alias")


def test_unknown_responder_raises_value_error():
    replay = TurnReplay(answers=[])
    with pytest.raises(ValueError):
        asyncio.run(
            replay.resolve(JudgmentRequest(prompt="?"), responder="not_a_real_responder")
        )
