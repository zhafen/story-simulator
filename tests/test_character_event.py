"""Tests for process_event's character-aware branch: decide_event only
runs for an NPC-controlled character's own event; a human-voiced
character's event, and an ordinary base-module event, both skip straight
to resolve_event unchanged.
"""

import asyncio

import pytest

from conftest import _make_ctx, update_registry
from story_simulator.mcp_server import advance_simulation, start_world

pytestmark = pytest.mark.slow


def _world(tmp_path, name="save"):
    ctx = _make_ctx()
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir(exist_ok=True)
    start_world(str(tmp_path / name), ctx, scenario_dir=str(scenario_dir))
    return ctx


def _schedule_character_event(ctx, event_alias: str, character_alias: str, start_time: float, duration: float) -> None:
    update_registry(
        f"{event_alias}:\n"
        f"    - event:\n"
        f"        start_time: {start_time}\n"
        f"        duration: {duration}\n"
        f"    - event_state:\n"
        f"        value: planned\n"
        f"    - involved_entity:\n"
        f"        value: {character_alias}\n",
        ctx=ctx,
    )


def _mark_resolved(ctx, alias: str) -> None:
    update_registry(
        f"{alias}:\n"
        f"    - outcome:\n"
        f"        value: {alias} resolved.\n"
        f"    - event_state:\n"
        f"        value: complete\n",
        ctx=ctx,
    )


def test_npc_event_pauses_for_decide_before_resolve(tmp_path, monkeypatch):
    """An NPC-flagged event must pause for decide_event's own responder
    (STORY_SIM_DECIDE_RESPONDER) before resolve_event ever asks anything."""
    monkeypatch.setenv("STORY_SIM_DECIDE_RESPONDER", "host")
    ctx = _world(tmp_path)
    update_registry("guard:\n    - character:\n        interaction_type: npc\n    - position: {x: 0, y: 0}\n", ctx=ctx)
    _schedule_character_event(ctx, "guard_event", "guard", 0, 0)

    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["step"] == "decide_event"
    assert "guard is deciding what to do next" in result["prompt"]
    assert "Do NOT call update_registry" in result["prompt"]

    result = asyncio.run(
        advance_simulation(ctx, resume_token=result["resume_token"], answer="The guard paces the corridor.")
    )
    assert result["status"] == "input_required"
    assert result["step"] == "resolve_event"
    assert "guard_event's end_time" in result["prompt"]
    assert "already been decided: 'The guard paces the corridor.'" in result["prompt"]


def test_human_voiced_character_event_skips_decide(tmp_path):
    """A player-controlled character's own event goes straight to
    resolve_event -- there's nothing to autonomously decide for them --
    but the resolve prompt itself must tell the host to actually ask the
    player if it doesn't already know their action (see
    resolve_event's own human_character_alias handling)."""
    ctx = _world(tmp_path)
    update_registry("hero:\n    - character:\n        interaction_type: player\n    - position: {x: 0, y: 0}\n", ctx=ctx)
    _schedule_character_event(ctx, "hero_event", "hero", 0, 0)

    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["step"] == "resolve_event"
    assert "hero_event's end_time" in result["prompt"]
    assert "already been decided" not in result["prompt"]
    assert "hero is the player's own character" in result["prompt"]
    assert "ask them directly before deciding" in result["prompt"]


def test_base_event_prompt_has_no_player_guidance(tmp_path):
    """An ordinary base-module event (no character involved at all) must
    not pick up the player-solicitation language meant only for a
    human-voiced character's own event."""
    ctx = _world(tmp_path)
    from tests.test_event_loop import _schedule_event  # reuse the base-event helper

    _schedule_event(ctx, "gizmo_event", 0, 0)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert "is the player's own character" not in result["prompt"]
    assert "ask them directly before deciding" not in result["prompt"]


def test_base_event_with_no_character_skips_decide(tmp_path):
    ctx = _world(tmp_path)
    from tests.test_event_loop import _schedule_event  # reuse the base-event helper

    _schedule_event(ctx, "gizmo_event", 0, 0)
    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert "gizmo_event's end_time" in result["prompt"]
    assert "already been decided" not in result["prompt"]


def test_npc_decide_uses_the_configured_decide_responder(tmp_path, monkeypatch):
    monkeypatch.setenv("STORY_SIM_DECIDE_RESPONDER", "subagent")
    ctx = _world(tmp_path)
    update_registry("guard:\n    - character:\n        interaction_type: npc\n    - position: {x: 0, y: 0}\n", ctx=ctx)
    _schedule_character_event(ctx, "guard_event", "guard", 0, 0)

    result = asyncio.run(advance_simulation(ctx))
    assert result["responder"] == "subagent"
    assert "own subagent mechanism" in result["prompt"]


def test_invalid_decide_responder_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("STORY_SIM_DECIDE_RESPONDER", "orchestrator")
    ctx = _world(tmp_path)
    update_registry("guard:\n    - character:\n        interaction_type: npc\n    - position: {x: 0, y: 0}\n", ctx=ctx)
    _schedule_character_event(ctx, "guard_event", "guard", 0, 0)
    with pytest.raises(ValueError, match="STORY_SIM_DECIDE_RESPONDER"):
        asyncio.run(advance_simulation(ctx))
