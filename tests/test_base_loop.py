"""Tests for the base event-driven simulation: advance_simulation with the
character module disabled (story_simulator.config.enabled_modules) -- no
characters, no NPCs, no physics/terrain modules, just whatever's been
scheduled via next_due, resolved by responder="host" each time it comes due.

These are the kind of scenario a base-module world can resolve without any
detailed physics: a chain of events that needs walking through step by
step, where "what happens next" is a plausible narrative judgment rather
than a calculation -- a Rube Goldberg machine (ball -> domino -> lever ->
switch) being the canonical example.
"""

import asyncio
from unittest.mock import MagicMock

from story_simulator.mcp_server import advance_simulation, start_world, update_registry


def _make_ctx():
    """Return a minimal mock Context whose session supports weak references."""
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


def _base_world(tmp_path, monkeypatch, name="save"):
    """Open a save seeded from nothing -- no player, no default scenario,
    no characters at all -- with the character module disabled, so
    advance_simulation runs its base branch (core.pop_event/
    process_base_event) instead of the character-ful one."""
    monkeypatch.setenv("STORY_SIM_MODULES", "")
    ctx = _make_ctx()
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir(exist_ok=True)
    start_world(str(tmp_path / name), ctx, scenario_dir=str(scenario_dir))
    return ctx


def test_nothing_scheduled_returns_done_immediately(tmp_path, monkeypatch):
    ctx = _base_world(tmp_path, monkeypatch)
    result = asyncio.run(advance_simulation(ctx))
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_responder_is_always_host(tmp_path, monkeypatch):
    """No character.interaction_type exists to branch on, and there's no
    subagent persona for a base-module event to fall back from -- unlike
    the character-ful branch, only "host" is ever possible here."""
    ctx = _base_world(tmp_path, monkeypatch)
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["responder"] == "host"
    assert "gizmo is due" in result["prompt"]


def test_self_rescheduling_chain_runs_to_completion(tmp_path, monkeypatch):
    """A single entity resolving itself repeatedly, walking through several
    steps of a Rube Goldberg machine, until an answer with no next_due_in
    line ends the chain -- core.pop_event then correctly never sees it
    again (pushed at due_at=inf)."""
    ctx = _base_world(tmp_path, monkeypatch)
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


def test_multi_entity_handoff_interleaves_by_due_time(tmp_path, monkeypatch):
    """Two independent Rube Goldberg chains, scheduled with different due
    times -- the loop must interleave them by when they're actually due,
    not exhaust one chain before ever touching the other, and a mid-chain
    handoff to a brand-new entity (chain_a_ball -> chain_a_domino) must
    slot into that same ordering correctly."""
    ctx = _base_world(tmp_path, monkeypatch)
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


def test_malformed_next_due_in_falls_back_to_never_due_again(tmp_path, monkeypatch):
    """Unlike the character module's branch (default=1.0, keep going), a
    base-module event with a malformed or missing next_due_in defaults to
    inf -- it has no standing agenda to fall back on acting from, so a
    model's mistake here ends the chain rather than looping it forever on
    a hardcoded interval."""
    ctx = _base_world(tmp_path, monkeypatch)
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)
    result = asyncio.run(advance_simulation(ctx))
    token = result["resume_token"]

    result = asyncio.run(
        advance_simulation(ctx, resume_token=token, answer="Something happens.\nnext_due_in: not-a-number")
    )
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_default_config_runs_the_character_branch_instead(tmp_path):
    """Sanity check on the module toggle itself: with STORY_SIM_MODULES
    unset (the default -- see enabled_modules), advance_simulation takes
    the character branch, not the base one, even for a world with no
    characters -- so it reports nothing scheduled rather than picking up a
    bare next_due row the way the base branch would."""
    ctx = _make_ctx()
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir()
    start_world(str(tmp_path / "save"), ctx, scenario_dir=str(scenario_dir))
    update_registry("gizmo:\n    - next_due:\n        value: 0\n", ctx)

    result = asyncio.run(advance_simulation(ctx))
    assert result == {"status": "done", "narration": "Nothing scheduled."}
