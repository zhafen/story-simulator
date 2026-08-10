"""Tests for the character/npc/physics/terrain optional-module tools.

Shelved alongside the code they test (perceive, generate_terrain,
resolve_physics, resolve_interaction, advance_npc_turn -- see
docs/architecture.md) when those were moved out of the live tool surface.
Outside `testpaths` (tests/), so not collected by pytest, and these
imports no longer resolve as-is (the names were removed from
mcp_server.py along with the tools) -- kept as reference for pulling this
back in, not as a runnable suite.
"""

import asyncio
from unittest.mock import MagicMock

from story_simulator.mcp_server import (
    _registrars,
    advance_npc_turn,
    generate_terrain,
    perceive,
    resolve_interaction,
    resolve_physics,
    start_world,
)


def _make_ctx():
    """Return a minimal mock Context whose session supports weak references."""
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# perceive
# ---------------------------------------------------------------------------


class TestPerceive:
    def test_reports_nothing_nearby_when_alone(self, tmp_path):
        scenario_dir = tmp_path / "scenario"
        scenario_dir.mkdir()
        (scenario_dir / "scenario.yaml").write_text(
            "solo:\n    - character:\n        interaction_type: player\n    - position: {x: 0, y: 0}\n"
        )
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx, scenario_dir=str(scenario_dir))
        result = perceive("solo", ctx)
        assert "Nothing else" in result

    def test_reports_nearby_entities(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = perceive("player", ctx)
        assert "door" in result

    def test_records_active_and_memory_tags(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        perceive("player", ctx)
        registrar = _registrars[ctx.request_context.session]
        active = registrar.view("active").execute()
        assert "door" in active["entity_id.alias"].values


# ---------------------------------------------------------------------------
# generate_terrain / resolve_physics
# ---------------------------------------------------------------------------


class TestSpecialistTools:
    def test_generate_terrain_delegates_to_terrain_agent(self, monkeypatch):
        fake_agent = MagicMock()
        fake_agent.generate.return_value = "A mossy clearing."
        monkeypatch.setattr("story_simulator.mcp_server._terrain_agent", fake_agent)

        result = generate_terrain("a clearing near the river")

        assert result == "A mossy clearing."
        fake_agent.generate.assert_called_once_with("a clearing near the river")

    def test_resolve_physics_delegates_to_physics_agent(self, monkeypatch):
        fake_agent = MagicMock()
        fake_agent.resolve.return_value = "The gap is narrow enough to clear."
        monkeypatch.setattr("story_simulator.mcp_server._physics_agent", fake_agent)

        result = resolve_physics("jumping a two-meter gap")

        assert result == "The gap is narrow enough to clear."
        fake_agent.resolve.assert_called_once_with("jumping a two-meter gap")

    def test_resolve_interaction_delegates_and_syncs_world_yaml(self, tmp_path, monkeypatch):
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx)
        mock_resolve = MagicMock(return_value="rock and window collide.")
        monkeypatch.setattr("story_simulator.mcp_server._resolve_interaction", mock_resolve)

        result = resolve_interaction(["rock", "window"], "a rock hits a window", ctx)

        assert result == "rock and window collide."
        (registrar, physics_agent, entity_ids, scenario, time), _ = mock_resolve.call_args
        assert entity_ids == ["rock", "window"]
        assert scenario == "a rock hits a window"
        assert (save_dir / "world" / "world.yaml").exists()


# ---------------------------------------------------------------------------
# advance_npc_turn
# ---------------------------------------------------------------------------


def _make_llm_response(content, tool_calls=None, finish_reason=None):
    if finish_reason is None:
        finish_reason = "tool_calls" if tool_calls else "stop"
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    dumped = {"role": "assistant", "content": content}
    if tool_calls:
        dumped["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in tool_calls
        ]
    message.model_dump.return_value = dumped
    choice = MagicMock(message=message, finish_reason=finish_reason)
    return MagicMock(choices=[choice])


class TestAdvanceNpcTurn:
    def test_decides_narrates_and_records(self, tmp_path, monkeypatch):
        ctx = _make_ctx()
        scenario_dir = tmp_path / "scenario"
        scenario_dir.mkdir()
        (scenario_dir / "scenario.yaml").write_text(
            "traveler:\n"
            "    - character:\n"
            "        interaction_type: npc\n"
            "    - position: {x: 0, y: 0}\n"
            "    - agenda: Explore.\n"
        )
        start_world(str(tmp_path / "save"), ctx, scenario_dir=str(scenario_dir))

        decide_response = _make_llm_response("I look around.")
        narrate_response = _make_llm_response("The traveler looks around and sees nothing new.")
        mock_completion = MagicMock(side_effect=[decide_response, narrate_response])
        monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

        result = asyncio.run(advance_npc_turn("traveler", ctx))

        assert "I look around." in result
        assert "traveler" in result
        assert mock_completion.call_count == 2
