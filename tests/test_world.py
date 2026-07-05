from unittest.mock import MagicMock

import pytest

from story_simulator.world import AgentWorld, World, MirrorWorld


def test_base_world_cannot_be_instantiated():
    with pytest.raises(TypeError):
        World()


def test_mirror_world_echoes_text():
    world = MirrorWorld()
    assert world.respond("hello there") == "hello there"


def test_agent_world_sends_text_and_returns_response(monkeypatch):
    text_block = MagicMock(type="text", text="hello back")
    mock_response = MagicMock(content=[text_block])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    monkeypatch.setattr("story_simulator.world.anthropic.Anthropic", lambda: mock_client)

    world = AgentWorld()
    result = world.respond("hello there")

    assert result == "hello back"
    mock_client.messages.create.assert_called_once_with(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "hello there"}],
    )
