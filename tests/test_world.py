from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from iacs.architect import Architect

from story_simulator.world import (
    AgentWorld,
    Archivist,
    IacsArchivist,
    World,
    MirrorWorld,
    EnsembleWorld,
    WORLD_YAML_FILENAME,
)


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


def test_archivist_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Archivist()


def test_ensemble_world_returns_world_soul_response():
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    world = EnsembleWorld(world_soul=world_soul)
    result = world.respond("open the door")

    assert result == "the world responds"
    world_soul.respond.assert_called_once_with("open the door")


def test_ensemble_world_passes_exchange_to_archivist():
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"
    archivist = MagicMock(spec=Archivist)

    world = EnsembleWorld(world_soul=world_soul, archivist=archivist)
    world.respond("open the door")

    archivist.record.assert_called_once_with("open the door", "the world responds")


def test_ensemble_world_works_without_an_archivist():
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"

    world = EnsembleWorld(world_soul=world_soul)

    assert world.respond("open the door") == "the world responds"


def test_ensemble_world_creates_an_architect_at_startup():
    world_soul = MagicMock(spec=World)

    world = EnsembleWorld(world_soul=world_soul)

    assert isinstance(world.architect, Architect)


def test_ensemble_world_architect_loads_from_save_dir(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    (save_dir / WORLD_YAML_FILENAME).write_text("player:\n    - origin\n")
    world_soul = MagicMock(spec=World)

    world = EnsembleWorld(world_soul=world_soul, save_dir=save_dir)

    assert world.architect.get("origin").count().execute() == 1


def test_ensemble_world_refreshes_architect_after_each_turn(tmp_path):
    save_dir = tmp_path / "save"
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"
    archivist = MagicMock(spec=Archivist)

    world = EnsembleWorld(world_soul=world_soul, archivist=archivist, save_dir=save_dir)
    assert world.architect.get("origin").count().execute() == 0

    def write_world_file(*_args):
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / WORLD_YAML_FILENAME).write_text("player:\n    - origin\n")

    archivist.record.side_effect = write_world_file
    world.respond("open the door")

    assert world.architect.get("origin").count().execute() == 1


def test_ensemble_world_defaults_to_iacs_archivist_when_save_dir_given(tmp_path):
    save_dir = tmp_path / "save"
    world_soul = MagicMock(spec=World)

    world = EnsembleWorld(world_soul=world_soul, save_dir=save_dir)

    assert isinstance(world.systems[0], IacsArchivist)
    assert world.systems[0].save_dir == save_dir


def test_ensemble_world_loops_over_all_systems():
    world_soul = MagicMock(spec=World)
    world_soul.respond.return_value = "the world responds"
    system_a = MagicMock(spec=Archivist)
    system_b = MagicMock(spec=Archivist)

    world = EnsembleWorld(world_soul=world_soul, archivist=system_a)
    world.systems.append(system_b)
    world.respond("open the door")

    system_a.record.assert_called_once_with("open the door", "the world responds")
    system_b.record.assert_called_once_with("open the door", "the world responds")


def _make_tool_use_block(tool_name, tool_input, block_id):
    block = MagicMock(type="tool_use", input=tool_input, id=block_id)
    block.name = tool_name
    return block


def test_iacs_archivist_reads_and_writes_world_file(tmp_path):
    archivist = IacsArchivist(tmp_path / "save")

    assert archivist._read_world_file() == "(world.yaml does not exist yet)"

    archivist._write_world_file("player:\n    - origin\n")

    assert archivist._read_world_file() == "player:\n    - origin\n"
    assert (archivist.save_dir / WORLD_YAML_FILENAME).read_text() == "player:\n    - origin\n"


def test_iacs_archivist_dispatches_mcp_and_local_tools(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"

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
    monkeypatch.setattr("story_simulator.world.anthropic.Anthropic", lambda **kwargs: mock_client)

    mcp_calls = []

    class FakeMcpSession:
        tools = [{"name": "describe_format", "description": "", "input_schema": {}}]

        async def call_tool(self, name, arguments):
            mcp_calls.append((name, arguments))
            return "format guide text"

    @asynccontextmanager
    async def fake_open_iacs_mcp_session(manifest_dir):
        yield FakeMcpSession()

    monkeypatch.setattr("story_simulator.world.open_iacs_mcp_session", fake_open_iacs_mcp_session)

    archivist = IacsArchivist(save_dir)
    archivist.record("I look around", "you see a door")

    assert mcp_calls == [("describe_format", {})]
    assert (save_dir / WORLD_YAML_FILENAME).read_text() == "player:\n    - origin\n"
    assert mock_client.messages.create.call_count == 3
