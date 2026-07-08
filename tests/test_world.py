from collections import OrderedDict
from unittest.mock import MagicMock

import pytest
from iacs.architect import Architect

from story_simulator.systems import (
    ArchivistAgentSystem,
    InputSystem,
    MapSystem,
    ResolverAgentSystem,
    System,
    VisualizerSystem,
    WORLD_YAML_FILENAME,
    _latest_input,
)
from story_simulator.world import AgentWorld, EnsembleWorld, World, MirrorWorld


def test_base_world_cannot_be_instantiated():
    with pytest.raises(TypeError):
        World()


def test_mirror_world_echoes_text():
    world = MirrorWorld()
    assert world.respond("hello there") == "hello there"


def _make_mock_client(session_id, events):
    text_block = MagicMock(type="text", text="hello back")
    message_event = MagicMock(type="agent.message", content=[text_block])
    idle_event = MagicMock(type="session.status_idle", stop_reason=MagicMock(type="end_turn"))

    mock_stream = MagicMock()
    mock_stream.__enter__.return_value = events or [message_event, idle_event]
    mock_stream.__exit__.return_value = False

    mock_client = MagicMock()
    mock_client.beta.sessions.create.return_value = MagicMock(id=session_id)
    mock_client.beta.sessions.events.stream.return_value = mock_stream
    return mock_client


def test_agent_world_creates_session_and_returns_response(monkeypatch):
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.world.anthropic.Anthropic", lambda **kwargs: mock_client)

    world = AgentWorld(agent_id="agent_test", environment_id="env_test")
    result = world.respond("hello there")

    assert result == "hello back"
    mock_client.beta.sessions.create.assert_called_once_with(
        agent="agent_test", environment_id="env_test"
    )
    mock_client.beta.sessions.events.send.assert_called_once_with(
        session_id="sesn_test123",
        events=[{"type": "user.message", "content": [{"type": "text", "text": "hello there"}]}],
    )


def test_agent_world_reuses_session_across_calls(monkeypatch):
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.world.anthropic.Anthropic", lambda **kwargs: mock_client)

    world = AgentWorld(agent_id="agent_test", environment_id="env_test")
    world.respond("first")
    world.respond("second")

    mock_client.beta.sessions.create.assert_called_once()


def test_agent_world_syncs_agent_config_from_repo_file(tmp_path, monkeypatch):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text("name: Test Agent\nmodel: claude-haiku-4-5\nsystem: Be terse.\n")

    mock_client = _make_mock_client("sesn_test123", events=None)
    mock_client.beta.agents.retrieve.return_value = MagicMock(version=3)
    monkeypatch.setattr("story_simulator.world.anthropic.Anthropic", lambda **kwargs: mock_client)

    world = AgentWorld(agent_id="agent_test", environment_id="env_test", config_path=config_path)
    world.respond("hello there")

    mock_client.beta.agents.retrieve.assert_called_once_with("agent_test")
    mock_client.beta.agents.update.assert_called_once_with(
        "agent_test",
        version=3,
        name="Test Agent",
        description="",
        model="claude-haiku-4-5",
        system="Be terse.",
        tools=[],
    )


def test_agent_world_inherits_system_from_prod_config_when_omitted(tmp_path, monkeypatch):
    prod_config_path = tmp_path / "agent.yaml"
    prod_config_path.write_text(
        "name: Prod Agent\nmodel: claude-opus-4-8\nsystem: Shared instructions.\n"
    )
    monkeypatch.setattr("story_simulator.world.PROD_AGENT_CONFIG_PATH", prod_config_path)

    test_config_path = tmp_path / "agent.test.yaml"
    test_config_path.write_text("name: Test Agent\nmodel: claude-haiku-4-5\n")

    mock_client = _make_mock_client("sesn_test123", events=None)
    mock_client.beta.agents.retrieve.return_value = MagicMock(version=1)
    monkeypatch.setattr("story_simulator.world.anthropic.Anthropic", lambda **kwargs: mock_client)

    world = AgentWorld(
        agent_id="agent_test", environment_id="env_test", config_path=test_config_path
    )
    world.respond("hello there")

    mock_client.beta.agents.update.assert_called_once_with(
        "agent_test",
        version=1,
        name="Test Agent",
        description="",
        model="claude-haiku-4-5",
        system="Shared instructions.",
        tools=[],
    )


# ---------------------------------------------------------------------------
# EnsembleWorld
# ---------------------------------------------------------------------------


def _write_world_yaml(save_dir, content):
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / WORLD_YAML_FILENAME).write_text(content)


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
"""


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
        system.step.assert_called_once_with(world.architect, world.save_dir, 1)


def test_ensemble_world_forwards_text_to_input_system(tmp_path):
    input_system = InputSystem()
    world = EnsembleWorld(systems=OrderedDict(input=input_system), save_dir=tmp_path / "save")

    world.respond("open the door")

    assert input_system._pending_text is None  # consumed by step()
    assert _latest_input(world.save_dir, "player", turn=1) == "open the door"


def test_ensemble_world_returns_resolvers_last_response(tmp_path, monkeypatch):
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    world = EnsembleWorld(
        systems=OrderedDict(input=InputSystem(), resolver=ResolverAgentSystem()),
        save_dir=tmp_path / "save",
    )

    assert world.respond("open the door") == "hello back"


def test_ensemble_world_returns_empty_string_without_save_dir(monkeypatch):
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    resolver = ResolverAgentSystem()
    world = EnsembleWorld(systems=OrderedDict(input=InputSystem(), resolver=resolver))

    assert world.respond("open the door") == ""
    mock_client.beta.sessions.create.assert_not_called()


def test_ensemble_world_returns_empty_string_without_a_resolver():
    world = EnsembleWorld(systems=OrderedDict())
    assert world.respond("open the door") == ""


def test_ensemble_world_full_turn_updates_active_entities_next_turn(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    def _record(architect, *_args):
        _write_world_yaml(save_dir, _SAMPLE_WORLD_YAML)
        architect.load_manifest(save_dir)

    archivist = MagicMock(spec=System)
    archivist.step.side_effect = _record

    systems = OrderedDict(
        map=MapSystem(radius=10.0),
        input=InputSystem(),
        resolver=ResolverAgentSystem(),
        archivist=archivist,
    )
    world = EnsembleWorld(systems=systems, save_dir=save_dir)

    def _sent_text():
        events = mock_client.beta.sessions.events.send.call_args.kwargs["events"]
        return events[0]["content"][0]["text"]

    world.respond("look around")
    assert _sent_text() == "look around"

    world.respond("say hello")

    prompt = _sent_text()
    assert "nearby_npc" in prompt
    assert prompt.endswith("Player input: say hello")
