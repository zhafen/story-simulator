from collections import OrderedDict
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from iacs.architect import Architect

from story_simulator.systems import (
    AgentSystem,
    ArchivistAgentSystem,
    EnsembleWorld,
    InputSystem,
    MapSystem,
    ResolverAgentSystem,
    System,
    VisualizerSystem,
    WORLD_YAML_FILENAME,
    _active_entities_for_turn,
    _latest_turn_value,
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


def test_input_system_writes_command_component(tmp_path):
    save_dir = tmp_path / "save"
    architect = Architect()

    InputSystem().step(architect, save_dir, turn=1, text="open the door")

    assert _latest_turn_value(save_dir, "command", turn=1) == "open the door"


def test_input_system_does_nothing_without_save_dir():
    architect = Architect()
    InputSystem().step(architect, None, turn=1, text="open the door")
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

    MapSystem().step(architect, save_dir, turn=1, text="look around")

    assert _active_entities_for_turn(save_dir, turn=1) == []


def test_map_system_tags_entities_within_radius(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)

    MapSystem(radius=10.0).step(architect, save_dir, turn=1, text="look around")

    active = _active_entities_for_turn(save_dir, turn=1)
    assert {"id": "nearby_npc", "kind": "character", "label": "npc"} in active
    assert not any(e["id"] == "distant_rock" for e in active)
    assert not any(e["id"] == "player" for e in active)


def test_map_system_excludes_entities_outside_radius(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)

    MapSystem(radius=1.0).step(architect, save_dir, turn=1, text="look around")

    assert _active_entities_for_turn(save_dir, turn=1) == []


# ---------------------------------------------------------------------------
# ResolverAgentSystem
# ---------------------------------------------------------------------------


def test_resolver_agent_system_calls_world_soul_and_records_narration(tmp_path):
    save_dir = tmp_path / "save"
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    resolver = ResolverAgentSystem(world_soul=world_soul)
    architect = Architect()
    InputSystem().step(architect, save_dir, turn=1, text="open the door")

    resolver.step(architect, save_dir, turn=1, text="open the door")

    world_soul.respond.assert_called_once_with("open the door")
    assert resolver.last_response == "the world responds"
    assert _latest_turn_value(save_dir, "narration", turn=1) == "the world responds"


def test_resolver_agent_system_includes_active_entities_in_prompt(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
    architect = Architect.from_manifest(save_dir)
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    MapSystem(radius=10.0).step(architect, save_dir, turn=1, text="look around")
    InputSystem().step(architect, save_dir, turn=1, text="look around")
    ResolverAgentSystem(world_soul=world_soul).step(architect, save_dir, turn=1, text="look around")

    prompt = world_soul.respond.call_args.args[0]
    assert "nearby_npc" in prompt
    assert prompt.endswith("Player input: look around")


def test_resolver_agent_system_works_without_save_dir():
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"
    resolver = ResolverAgentSystem(world_soul=world_soul)

    resolver.step(Architect(), None, turn=1, text="open the door")

    world_soul.respond.assert_called_once_with("open the door")
    assert resolver.last_response == "the world responds"


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
    InputSystem().step(architect, save_dir, turn=1, text="open the door")

    ArchivistAgentSystem().step(architect, save_dir, turn=1, text="open the door")

    assert not (save_dir / WORLD_YAML_FILENAME).exists()


def test_archivist_agent_system_dispatches_mcp_and_local_tools(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    architect = Architect()
    InputSystem().step(architect, save_dir, turn=1, text="I look around")
    ResolverAgentSystem(world_soul=MagicMock(respond=lambda text: "you see a door")).step(
        architect, save_dir, turn=1, text="I look around"
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

    ArchivistAgentSystem().step(architect, save_dir, turn=1, text="I look around")

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

    VisualizerSystem(render_path=render_path).step(architect, save_dir, turn=1, text="look")

    assert calls == [(architect, render_path)]


def test_visualizer_system_does_nothing_without_save_dir(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "story_simulator.systems.render_positions", lambda a, p: calls.append((a, p))
    )

    VisualizerSystem().step(Architect(), None, turn=1, text="look")

    assert calls == []


# ---------------------------------------------------------------------------
# EnsembleWorld
# ---------------------------------------------------------------------------


def test_ensemble_world_creates_an_architect_at_startup():
    world = EnsembleWorld(systems=OrderedDict())
    assert isinstance(world.architect, Architect)


def test_ensemble_world_architect_loads_from_save_dir(tmp_path):
    save_dir = tmp_path / "save"
    _write_world_yaml(save_dir, "player:\n    - origin\n")

    world = EnsembleWorld(systems=OrderedDict(), save_dir=save_dir)

    assert world.architect.get("origin").count().execute() == 1


def test_ensemble_world_default_systems_run_in_order(tmp_path):
    world = EnsembleWorld(save_dir=tmp_path / "save")
    assert list(world.systems) == ["map", "input", "resolver", "archivist", "visualizer"]
    assert isinstance(world.systems["map"], MapSystem)
    assert isinstance(world.systems["input"], InputSystem)
    assert isinstance(world.systems["resolver"], ResolverAgentSystem)
    assert isinstance(world.systems["archivist"], ArchivistAgentSystem)
    assert isinstance(world.systems["visualizer"], VisualizerSystem)


def test_ensemble_world_loops_over_all_systems_in_order():
    calls = []

    def _make_system(name):
        system = MagicMock(spec=System)
        system.step.side_effect = lambda *args: calls.append(name)
        return system

    systems = OrderedDict(a=_make_system("a"), b=_make_system("b"), c=_make_system("c"))
    world = EnsembleWorld(systems=systems)

    world.respond("open the door")

    assert calls == ["a", "b", "c"]
    for system in systems.values():
        system.step.assert_called_once_with(world.architect, world.save_dir, 1, "open the door")


def test_ensemble_world_returns_resolvers_last_response():
    resolver = ResolverAgentSystem(world_soul=MagicMock(respond=lambda text: "the world responds"))
    world = EnsembleWorld(systems=OrderedDict(resolver=resolver))

    assert world.respond("open the door") == "the world responds"


def test_ensemble_world_returns_empty_string_without_a_resolver():
    world = EnsembleWorld(systems=OrderedDict())
    assert world.respond("open the door") == ""


def test_ensemble_world_full_turn_updates_active_entities_next_turn(tmp_path):
    save_dir = tmp_path / "save"
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    def _record(architect, *_args):
        _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
        architect.load_manifest(save_dir)

    archivist = MagicMock(spec=System)
    archivist.step.side_effect = _record

    systems = OrderedDict(
        map=MapSystem(radius=10.0),
        input=InputSystem(),
        resolver=ResolverAgentSystem(world_soul=world_soul),
        archivist=archivist,
    )
    world = EnsembleWorld(systems=systems, save_dir=save_dir)

    world.respond("look around")
    world_soul.respond.assert_called_with("look around")

    world.respond("say hello")

    prompt = world_soul.respond.call_args.args[0]
    assert "nearby_npc" in prompt
    assert prompt.endswith("Player input: say hello")
