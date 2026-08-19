"""Tests for the event-driven simulation: advance_simulation resolving
`event` entities one at a time.

Via two separate responder calls per event -- resolve, then plan --
each by responder="host" (default) or "subagent" (STORY_SIM_RESPONDER).

These are the kind of scenario this loop can resolve without any detailed
physics: a chain of events that needs walking through step by step, where
"what happens next" is a plausible narrative judgment rather than a
calculation -- a Rube Goldberg machine (ball -> domino -> lever -> switch)
being the canonical example. There's no next_due_in convention anymore:
"what happens next" means the plan step creating a new `event` entity via
update_registry, the same direct tool-calling pattern a real responder
uses -- these tests do that by hand, simulating what a real host would do
in response to each prompt, since resolve_event/plan_events don't apply
anything on the responder's behalf (see core.py's own docstrings).
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


def _world(tmp_path, name="save"):
    """Open a save seeded from nothing -- no player, no default scenario,
    no characters at all."""
    ctx = _make_ctx()
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir(exist_ok=True)
    start_world(str(tmp_path / name), ctx, scenario_dir=str(scenario_dir))
    return ctx


def _schedule_event(ctx, alias: str, start_time: float, duration: float) -> None:
    """Create a new, already-planned event entity, the way a scenario or
    a plan step would."""
    update_registry(
        f"{alias}:\n"
        f"    - event:\n"
        f"        start_time: {start_time}\n"
        f"        duration: {duration}\n"
        f"    - event_state:\n"
        f"        value: planned\n",
        ctx=ctx,
    )


def _mark_resolved(ctx, alias: str, progress: str = "complete") -> None:
    """Simulate what a real host records on a resolve prompt: the event's
    own outcome and its own lifecycle transition, both via update_registry."""
    update_registry(
        f"{alias}:\n"
        f"    - outcome:\n"
        f"        progress: {progress}\n"
        f"        value: {alias} resolved.\n"
        f"    - event_state:\n"
        f"        value: {progress}\n",
        ctx=ctx,
    )


def test_nothing_scheduled_returns_done_immediately(tmp_path):
    ctx = _world(tmp_path)
    result = asyncio.run(advance_simulation(ctx))
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_responder_defaults_to_host(tmp_path):
    """No STORY_SIM_RESPONDER override -- "host" is config.event_responder()'s
    default, asked once an event's end_time is reached."""
    ctx = _world(tmp_path)
    _schedule_event(ctx, "gizmo_event", 0, 0)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["responder"] == "host"
    assert "gizmo_event's end_time" in result["prompt"]


def test_responder_can_be_configured_to_subagent(tmp_path, monkeypatch):
    """STORY_SIM_RESPONDER=subagent makes an event's resolve step ask via
    responder="subagent" instead.

    With a prompt that tells the connected host to delegate rather than
    answer inline -- see story_simulator.resolve._frame_for_responder.
    """
    monkeypatch.setenv("STORY_SIM_RESPONDER", "subagent")
    ctx = _world(tmp_path)
    _schedule_event(ctx, "gizmo_event", 0, 0)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["responder"] == "subagent"
    assert "own subagent mechanism" in result["prompt"]
    assert "gizmo_event's end_time" in result["prompt"]


def test_invalid_responder_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("STORY_SIM_RESPONDER", "orchestrator")
    ctx = _world(tmp_path)
    _schedule_event(ctx, "gizmo_event", 0, 0)
    with pytest.raises(ValueError, match="STORY_SIM_RESPONDER"):
        asyncio.run(advance_simulation(ctx))


def test_one_event_pauses_for_both_resolve_and_plan_before_finishing(tmp_path):
    """A single event goes through two separate pauses -- resolve, then
    plan -- before the loop reports done, even with nothing new scheduled."""
    ctx = _world(tmp_path)
    _schedule_event(ctx, "gizmo_event", 0, 0)

    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert "gizmo_event's end_time" in result["prompt"]

    _mark_resolved(ctx, "gizmo_event")
    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="Gizmo did its thing.")
    )
    assert result["status"] == "input_required"
    assert "gizmo_event just resolved" in result["prompt"]

    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="Nothing new needed.")
    )
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_plan_step_creates_a_new_event_that_gets_picked_up_next(tmp_path):
    """The plan step's own update_registry call (simulating what a real
    responder does) is what schedules a follow-up.

    There's no next_due_in line to parse anymore -- a brand-new event
    created there is exactly as poppable as one pre-planned from the start.
    """
    ctx = _world(tmp_path)
    _schedule_event(ctx, "ball_event", 0, 0)

    result = asyncio.run(advance_simulation(ctx))
    _mark_resolved(ctx, "ball_event")
    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="The ball rolls into the domino.")
    )
    assert "ball_event just resolved" in result["prompt"]

    # Simulate the responder scheduling a follow-up event during planning.
    _schedule_event(ctx, "domino_event", 1, 0)
    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="Scheduled domino_event next.")
    )
    assert result["status"] == "input_required"
    assert "domino_event's end_time" in result["prompt"]

    _mark_resolved(ctx, "domino_event")
    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="The domino topples the lever.")
    )
    assert "domino_event just resolved" in result["prompt"]
    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="Nothing new needed.")
    )
    assert result == {"status": "done", "narration": "Nothing scheduled."}


def test_world_time_persists_across_a_reconnect(tmp_path):
    """The bug this guards against: world time used to be purely
    in-process, session-scoped memory (core._current_world_time).

    So it reset to 0.0 on every reconnect -- even an idle-triggered MCP
    disconnect, which CLAUDE.md documents as routine, not just a crash --
    even though the world itself (Postgres) had already moved forward. A
    fresh session opening the same save_dir must see world time where the
    old session left it, not back at 0.0 (see docs/manifest/history.yaml:
    project_history.world_clock_persisted).
    """
    from story_simulator.core import _get_registrar, _next_time_stamp

    save_dir = tmp_path / "save"
    ctx = _world(tmp_path)
    _schedule_event(ctx, "gizmo_event", 10, 5)  # end_time = 15

    result = asyncio.run(advance_simulation(ctx))
    _mark_resolved(ctx, "gizmo_event")
    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="Gizmo did its thing.")
    )
    asyncio.run(advance_simulation(ctx, resume_token=result["resume_token"], answer="Nothing new needed."))

    assert _next_time_stamp(_get_registrar(ctx.request_context.session)) == 15.0

    ctx2 = _make_ctx()
    start_world(str(save_dir), ctx2)
    assert _next_time_stamp(_get_registrar(ctx2.request_context.session)) == 15.0


def _drive_loop_recording_order(ctx, result, on_plan) -> list[tuple[str, str]]:
    """Drive advance_simulation to completion, recording (step, alias)
    for every pause.

    "resolve" answered by marking the event resolved, "plan" answered
    by calling on_plan(alias) for test-specific behavior (e.g.
    scheduling a follow-up) and always finishing with "nothing new".
    """
    order: list[tuple[str, str]] = []
    while result["status"] == "input_required":
        # The prompt is framed with responder="host" instructions ahead of the
        # actual body -- pull the alias from before its own marker phrase.
        if "'s end_time" in result["prompt"]:
            who = result["prompt"].split("'s end_time")[0].rsplit("\n\n", 1)[-1]
            order.append(("resolve", who))
            _mark_resolved(ctx, who)
            answer = f"{who} resolves."
        else:
            # "...\n\nGiven how {alias} just resolved..." -- alias is the last
            # whitespace-separated token before the marker phrase.
            who = result["prompt"].split(" just resolved")[0].split()[-1]
            order.append(("plan", who))
            answer = on_plan(who)
        result = asyncio.run(advance_simulation(ctx, resume_token=result["resume_token"], answer=answer))
    assert result == {"status": "done", "narration": "Nothing scheduled."}
    return order


def test_multi_event_interleaves_by_end_time(tmp_path):
    """Two independently-scheduled events must interleave by their actual
    end_time, not exhaust one before ever touching the other."""
    ctx = _world(tmp_path)
    _schedule_event(ctx, "chain_a_event", 0, 0)
    _schedule_event(ctx, "chain_b_event", 5, 0)

    result = asyncio.run(advance_simulation(ctx))
    order = _drive_loop_recording_order(ctx, result, on_plan=lambda who: "Nothing new needed.")

    assert order == [
        ("resolve", "chain_a_event"),
        ("plan", "chain_a_event"),
        ("resolve", "chain_b_event"),
        ("plan", "chain_b_event"),
    ]


def test_multi_event_handoff_to_a_new_event_slots_in_by_end_time(tmp_path):
    """A mid-chain handoff (chain_a_ball_event's plan step schedules
    chain_a_domino_event, whose end_time comes sooner than
    chain_b_ball_event's) must slot into the loop's ordering correctly,
    not just append to the end."""
    ctx = _world(tmp_path)
    _schedule_event(ctx, "chain_a_ball_event", 0, 0)
    _schedule_event(ctx, "chain_b_ball_event", 5, 0)

    def on_plan(who):
        if who == "chain_a_ball_event":
            _schedule_event(ctx, "chain_a_domino_event", 1, 0)
            return "Scheduled chain_a_domino_event, end_time sooner than chain_b_ball_event."
        return "Nothing new needed."

    result = asyncio.run(advance_simulation(ctx))
    order = _drive_loop_recording_order(ctx, result, on_plan=on_plan)

    assert order == [
        ("resolve", "chain_a_ball_event"),
        ("plan", "chain_a_ball_event"),
        ("resolve", "chain_a_domino_event"),
        ("plan", "chain_a_domino_event"),
        ("resolve", "chain_b_ball_event"),
        ("plan", "chain_b_ball_event"),
    ]
