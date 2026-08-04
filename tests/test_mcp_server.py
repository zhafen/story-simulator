from unittest.mock import MagicMock

import pytest

from story_simulator.config import LIVING_WORLD_DIR
from story_simulator.mcp_server import (
    _get_registrar,
    _registrars,
    _save_dirs,
    advance_npc_turn,
    generate_terrain,
    perceive,
    resolve_physics,
    server,
    start_world,
    update_registry,
    view_entity,
    view_registry,
)


def _make_ctx():
    """Return a minimal mock Context whose session supports weak references."""
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# MCP tool registration smoke tests
# ---------------------------------------------------------------------------


class TestMcpToolRegistration:
    def _tool_names(self):
        return {t.name for t in server._tool_manager.list_tools()}

    def test_all_tools_are_registered(self):
        expected = {
            "start_world",
            "view_registry",
            "view_entity",
            "update_registry",
            "perceive",
            "generate_terrain",
            "resolve_physics",
            "advance_npc_turn",
        }
        assert expected <= self._tool_names()

    def test_generate_terrain_has_no_ctx_parameter(self):
        """generate_terrain/resolve_physics don't touch the registry, so no ctx is needed."""
        tools = {t.name: t for t in server._tool_manager.list_tools()}
        assert "ctx" not in tools["generate_terrain"].parameters.get("properties", {})


# ---------------------------------------------------------------------------
# start_world
# ---------------------------------------------------------------------------


class TestStartWorld:
    def test_returns_confirmation_string(self, tmp_path):
        ctx = _make_ctx()
        result = start_world(str(tmp_path / "save"), ctx)
        assert "World opened" in result

    def test_seeds_from_default_world_by_default(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert "origin" in registrar.registry.component_types

    def test_seeds_from_given_scenario_dir(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx, scenario_dir=str(LIVING_WORLD_DIR))
        registrar = _registrars[ctx.request_context.session]
        positions = registrar.view_df("position")
        assert "journaling_desk.journal" in positions["entity_id.alias"].values

    def test_stores_registrar_and_save_dir_for_session(self, tmp_path):
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx)
        assert ctx.request_context.session in _registrars
        assert _save_dirs[ctx.request_context.session] == save_dir

    def test_does_not_reseed_an_already_populated_save_dir(self, tmp_path):
        save_dir = tmp_path / "save"
        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        update_registry("custom_entity:\n    - origin\n", ctx)

        ctx2 = _make_ctx()
        start_world(str(save_dir), ctx2)
        registrar = _registrars[ctx2.request_context.session]
        assert registrar.get("origin").count().execute() == 2  # world's + custom_entity's

    def test_first_open_loads_only_world_history_dir_when_present(self, tmp_path):
        """world_history/, world/, and the seed are all redundant with each
        other -- loading more than one at once risks silently discarding data
        (YAML's last-key-wins on duplicate top-level keys) rather than
        merging it. world_history/ is the fullest, so it wins alone. Each
        directory can hold more than one yaml file (a save's author is free
        to split it up), so the loader must recurse into whichever it picks.
        """
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        (save_dir / "scenario.yaml").write_text("seed_only:\n    - origin\n")
        (save_dir / "world").mkdir()
        (save_dir / "world" / "world.yaml").write_text("world_only:\n    - origin\n")
        (save_dir / "world_history").mkdir()
        (save_dir / "world_history" / "a.yaml").write_text("history_a:\n    - origin\n")
        (save_dir / "world_history" / "nested").mkdir()
        (save_dir / "world_history" / "nested" / "b.yaml").write_text(
            "history_b:\n    - origin\n"
        )

        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("history_a") is not None
        assert registrar.get_entity_id("history_b") is not None
        assert registrar.get_entity_id("world_only") is None
        assert registrar.get_entity_id("seed_only") is None

    def test_first_open_loads_only_world_dir_when_no_history_dir(self, tmp_path):
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        (save_dir / "scenario.yaml").write_text("seed_only:\n    - origin\n")
        (save_dir / "world").mkdir()
        (save_dir / "world" / "world.yaml").write_text("world_only:\n    - origin\n")

        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("world_only") is not None
        assert registrar.get_entity_id("seed_only") is None

    def test_first_open_falls_back_to_recursive_glob_when_neither_dir_exists(self, tmp_path):
        """A pristine, never-yet-exported scenario_dir may be organized across
        several files at arbitrary depth -- with no world/ or world_history/
        subdirectory yet, everything under save_dir should still load.
        """
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        (save_dir / "scenario.yaml").write_text("seed_a:\n    - origin\n")
        (save_dir / "locations").mkdir()
        (save_dir / "locations" / "field.yaml").write_text("seed_b:\n    - origin\n")

        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("seed_a") is not None
        assert registrar.get_entity_id("seed_b") is not None


# ---------------------------------------------------------------------------
# view_registry / view_entity / update_registry
# ---------------------------------------------------------------------------


class TestRegistryTools:
    def test_get_registrar_errors_before_start_world(self):
        ctx = _make_ctx()
        with pytest.raises(ValueError, match="start_world"):
            _get_registrar(ctx)

    def test_view_registry_returns_csv_of_positions(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = view_registry("position", ctx)
        assert "player" in result

    def test_update_registry_merges_new_entity(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = update_registry("new_thing:\n    - origin\n", ctx)
        assert "Merged" in result
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get("origin").count().execute() == 2

    def test_update_registry_writes_collapsed_and_full_history_yaml(self, tmp_path):
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx)
        update_registry("door:\n    - description: first\n", ctx)
        update_registry("door:\n    - description: second\n", ctx)

        world_text = (save_dir / "world" / "world.yaml").read_text()
        assert "second" in world_text
        assert "first" not in world_text

        history_text = (save_dir / "world_history" / "world.yaml").read_text()
        assert "second" in history_text
        assert "first" in history_text

    def test_view_entity_returns_known_component_data(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = view_entity("player", ctx)
        assert "character" in result

    def test_view_entity_reports_unknown_entity(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = view_entity("nonexistent_xyz", ctx)
        assert "No data found" in result


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

        result = advance_npc_turn("traveler", ctx)

        assert "I look around." in result
        assert "traveler" in result
        assert mock_completion.call_count == 2
