"""Tests for the event-driven simulation: advance_simulation resolving
whatever's been scheduled via next_due, one due entity at a time, by
responder="host" (default) or "subagent" (STORY_SIM_BASE_RESPONDER) each
time it comes due.

These are the kind of scenario this loop can resolve without any detailed
physics: a chain of events that needs walking through step by step, where
"what happens next" is a plausible narrative judgment rather than a
calculation -- a Rube Goldberg machine (ball -> domino -> lever -> switch)
being the canonical example.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from story_simulator.mcp_server import advance_simulation, start_world, update_registry


def _make_ctx():
    """Return a minimal mock Context whose session supports weak references."""
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


def _base_world(tmp_path, name="save"):
    """Open a save seeded from nothing -- no player, no default scenario,
    no characters at all."""
    ctx = _make_ctx()
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir(exist_ok=True)
    start_world(str(tmp_path / name), ctx, scenario_dir=str(scenario_dir))
    return ctx


def test_nothing_scheduled_returns_done_immediately(tmp_path):
    ctx = _base_world(tmp_path)
    result = asyncio.run(advance_simulation(ctx))
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_responder_defaults_to_host(tmp_path):
    """No STORY_SIM_BASE_RESPONDER override -- "host" is config.base_event_responder()'s
    default, so that's what a due base event asks."""
    ctx = _base_world(tmp_path)
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["responder"] == "host"
    assert "gizmo is due" in result["prompt"]


def test_responder_can_be_configured_to_subagent(tmp_path, monkeypatch):
    """STORY_SIM_BASE_RESPONDER=subagent makes a due base event ask via
    responder="subagent" instead, with a prompt that tells the connected
    host to delegate rather than answer inline -- see
    story_simulator.resolve._frame_for_responder."""
    monkeypatch.setenv("STORY_SIM_BASE_RESPONDER", "subagent")
    ctx = _base_world(tmp_path)
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["responder"] == "subagent"
    assert "own subagent mechanism" in result["prompt"]
    assert "gizmo is due" in result["prompt"]


def test_invalid_base_responder_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("STORY_SIM_BASE_RESPONDER", "orchestrator")
    ctx = _base_world(tmp_path)
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)
    with pytest.raises(ValueError, match="STORY_SIM_BASE_RESPONDER"):
        asyncio.run(advance_simulation(ctx))


def test_self_rescheduling_chain_runs_to_completion(tmp_path):
    """A single entity resolving itself repeatedly, walking through several
    steps of a Rube Goldberg machine, until an answer with no next_due_in
    line ends the chain -- core.pop_event then correctly never sees it
    again (pushed at due_at=inf)."""
    ctx = _base_world(tmp_path)
    update_registry("ball:\n    - next_due:\n        value: 0\n", ctx)

    answers = [
        "The ball rolls down the ramp and knocks over the first domino.\nnext_due_in: 2",
        "The domino chain topples into a lever, flipping it.\nnext_due_in: 1",
        "The lever releases a weight, which drops onto a switch.\nnext_due_in: 1",
        "The switch clicks and the light turns on. Nothing left to happen.",
    ]

    result = asyncio.run(advance_simulation(ctx))
    for answer in answers:
        assert result["status"] == "input_required"
        token = result["resume_token"]
        result = asyncio.run(advance_simulation(ctx, resume_token=token, answer=answer))

    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_multi_entity_handoff_interleaves_by_due_time(tmp_path):
    """Two independent Rube Goldberg chains, scheduled with different due
    times -- the loop must interleave them by when they're actually due,
    not exhaust one chain before ever touching the other, and a mid-chain
    handoff to a brand-new entity (chain_a_ball -> chain_a_domino) must
    slot into that same ordering correctly."""
    ctx = _base_world(tmp_path)
    update_registry("chain_a_ball:\n    - next_due:\n        value: 0\n", ctx)
    update_registry("chain_b_ball:\n    - next_due:\n        value: 5\n", ctx)

    order = []
    result = asyncio.run(advance_simulation(ctx))
    while result["status"] == "input_required":
        who = result["prompt"].split(" ", 1)[0]
        order.append(who)
        token = result["resume_token"]
        if who == "chain_a_ball":
            # Hands off to a new entity due sooner than chain_b_ball, then
            # itself terminates (no next_due_in).
            update_registry("chain_a_domino:\n    - next_due:\n        value: 1\n", ctx)
            answer = "The a-ball rolls into the a-domino."
        else:
            answer = f"{who} resolves. Nothing more."
        result = asyncio.run(advance_simulation(ctx, resume_token=token, answer=answer))

    assert order == ["chain_a_ball", "chain_a_domino", "chain_b_ball"]
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_malformed_next_due_in_falls_back_to_never_due_again(tmp_path):
    """An event with a malformed or missing next_due_in defaults to inf --
    it has no standing agenda to fall back on acting from, so a model's
    mistake here ends the chain rather than looping it forever on a
    hardcoded interval."""
    ctx = _base_world(tmp_path)
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)
    result = asyncio.run(advance_simulation(ctx))
    token = result["resume_token"]

    result = asyncio.run(
        advance_simulation(ctx, resume_token=token, answer="Something happens.\nnext_due_in: not-a-number")
    )
    assert result == {"status": "done", "narration": "Nothing scheduled."}
