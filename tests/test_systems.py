from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from iacs.architect import Architect

from story_simulator.systems import (
    AgentSystem,
    ArchivistAgentSystem,
    InputSystem,
    MapSystem,
    ResolverAgentSystem,
    System,
    VisualizerSystem,
    WORLD_YAML_FILENAME,
    _active_aliases,
    _latest_input,
)
from story_simulator.world import World


def test_system_cannot_be_instantiated():
    with pytest.raises(TypeError):
        System()


def test_agent_system_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AgentSystem()


# ---------------------------------------------------------------------------
# InputSystem
# ---------------------------------------------------------------------------


def test_input_system_writes_input_component_on_player_entity(tmp_path):
    save_dir = tmp_path / "save"
    architect = Architect()

    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(architect, save_dir, turn=1)

    assert _latest_input(save_dir, "player", turn=1) == "open the door"


def test_input_system_does_nothing_without_pending_text(tmp_path):
    save_dir = tmp_path / "save"
    architect = Architect()

    InputSystem().step(architect, save_dir, turn=1)

    assert _latest_input(save_dir, "player", turn=1) is None


def test_input_system_does_nothing_without_save_dir():
    architect = Architect()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(architect, None, turn=1)
    # No exception, and nothing to assert against since there's no save_dir.


# ---------------------------------------------------------------------------
# MapSystem
# ---------------------------------------------------------------------------

_SAMPLE_WORLD_YAML = """
player:
    - character:
        interaction_type: player
    - position:
        x: 0.0
        y: 0.0

nearby_npc:
    - character:
        interaction_type: npc
    - position:
        x: 3.0
        y: 4.0

distant_rock:
    - object:
        type: rock
    - position:
        x: 500.0
        y: 0.0
"""


def _write_world_yaml(save_dir, content):
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / WORLD_YAML_FILENAME).write_text(content)


def test_map_system_does_nothing_without_player_data(tmp_path):
    save_dir = tmp_path / "save"
    architect = Architect()

    MapSystem().step(architect, save_dir, turn=1)

    assert _active_aliases(save_dir) == set()


def test_map_system_tags_entities_within_radius(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)

    MapSystem(radius=10.0).step(architect, save_dir, turn=1)

    assert _active_aliases(save_dir) == {"nearby_npc"}


def test_map_system_excludes_entities_outside_radius(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)

    MapSystem(radius=1.0).step(architect, save_dir, turn=1)

    assert _active_aliases(save_dir) == set()


def test_map_system_untags_entities_that_leave_radius(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)
    MapSystem(radius=10.0).step(architect, save_dir, turn=1)
    assert _active_aliases(save_dir) == {"nearby_npc"}

    MapSystem(radius=1.0).step(architect, save_dir, turn=2)

    assert _active_aliases(save_dir) == set()


# ---------------------------------------------------------------------------
# ResolverAgentSystem
# ---------------------------------------------------------------------------


def test_resolver_agent_system_calls_world_soul_and_records_reply(tmp_path):
    save_dir = tmp_path / "save"
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    resolver = ResolverAgentSystem(world_soul=world_soul)
    architect = Architect()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(architect, save_dir, turn=1)

    resolver.step(architect, save_dir, turn=1)

    world_soul.respond.assert_called_once_with("open the door")
    assert resolver.last_response == "the world responds"
    assert _latest_input(save_dir, "agent", turn=1) == "the world responds"


def test_resolver_agent_system_includes_active_entities_in_prompt(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    MapSystem(radius=10.0).step(architect, save_dir, turn=1)
    input_system = InputSystem()
    input_system.receive("look around")
    input_system.step(architect, save_dir, turn=1)
    ResolverAgentSystem(world_soul=world_soul).step(architect, save_dir, turn=1)

    prompt = world_soul.respond.call_args.args[0]
    assert prompt == "Active entities nearby: nearby_npc\nPlayer input: look around"


def test_resolver_agent_system_does_nothing_without_command(tmp_path):
    save_dir = tmp_path / "save"
    world_soul = MagicMock(spec=World)

    ResolverAgentSystem(world_soul=world_soul).step(Architect(), save_dir, turn=1)

    world_soul.respond.assert_not_called()


def test_resolver_agent_system_does_nothing_without_save_dir():
    world_soul = MagicMock(spec=World)
    resolver = ResolverAgentSystem(world_soul=world_soul)

    resolver.step(Architect(), None, turn=1)

    world_soul.respond.assert_not_called()


# ---------------------------------------------------------------------------
# ArchivistAgentSystem
# ---------------------------------------------------------------------------


def _make_tool_use_block(tool_name, tool_input, block_id):
    block = MagicMock(type="tool_use", input=tool_input, id=block_id)
    block.name = tool_name
    return block


def test_archivist_agent_system_does_nothing_without_narration(tmp_path):
    save_dir = tmp_path / "save"
    architect = Architect()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(architect, save_dir, turn=1)
    world_yaml_before = (save_dir / WORLD_YAML_FILENAME).read_text()

    ArchivistAgentSystem().step(architect, save_dir, turn=1)

    # InputSystem seeds/writes world.yaml itself, but the Archivist's own
    # LLM tool loop should never have run without a narration to transcribe.
    assert (save_dir / WORLD_YAML_FILENAME).read_text() == world_yaml_before


def test_archivist_agent_system_dispatches_mcp_and_local_tools(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    architect = Architect()
    input_system = InputSystem()
    input_system.receive("I look around")
    input_system.step(architect, save_dir, turn=1)
    ResolverAgentSystem(world_soul=MagicMock(respond=lambda text: "you see a door")).step(
        architect, save_dir, turn=1
    )

    mcp_tool_use = _make_tool_use_block("describe_format", {}, "tool_1")
    write_tool_use = _make_tool_use_block(
        "write_world_file", {"content": "player:\n    - origin\n"}, "tool_2"
    )
    final_text = MagicMock(type="text", text="done")

    responses = [
        MagicMock(content=[mcp_tool_use], stop_reason="tool_use"),
        MagicMock(content=[write_tool_use], stop_reason="tool_use"),
        MagicMock(content=[final_text], stop_reason="end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    mcp_calls = []

    class FakeMcpSession:
        tools = [{"name": "describe_format", "description": "", "input_schema": {}}]

        async def call_tool(self, name, arguments):
            mcp_calls.append((name, arguments))
            return "format guide text"

    @asynccontextmanager
    async def fake_open_iacs_mcp_session(manifest_dir):
        yield FakeMcpSession()

    monkeypatch.setattr(
        "story_simulator.systems.open_iacs_mcp_session", fake_open_iacs_mcp_session
    )

    ArchivistAgentSystem().step(architect, save_dir, turn=1)

    assert mcp_calls == [("describe_format", {})]
    assert (save_dir / WORLD_YAML_FILENAME).read_text() == "player:\n    - origin\n"
    assert mock_client.messages.create.call_count == 3
    assert architect.get("origin").count().execute() == 1


# ---------------------------------------------------------------------------
# VisualizerSystem
# ---------------------------------------------------------------------------


def test_visualizer_system_renders_positions(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    render_path = tmp_path / "render.svg"
    architect = Architect()

    calls = []
    monkeypatch.setattr(
        "story_simulator.systems.render_positions", lambda a, p: calls.append((a, p))
    )

    VisualizerSystem(render_path=render_path).step(architect, save_dir, turn=1)

    assert calls == [(architect, render_path)]


def test_visualizer_system_does_nothing_without_save_dir(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "story_simulator.systems.render_positions", lambda a, p: calls.append((a, p))
    )

    VisualizerSystem().step(Architect(), None, turn=1)

    assert calls == []
