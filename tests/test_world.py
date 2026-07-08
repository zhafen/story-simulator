from unittest.mock import MagicMock

import pytest

from story_simulator.world import AgentWorld, World, MirrorWorld


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
