from unittest.mock import MagicMock, patch

from story_simulator.agent import ask_agent


def test_ask_agent_returns_text_from_response():
    text_block = MagicMock(type="text", text="Hello there!")
    mock_response = MagicMock(content=[text_block])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("story_simulator.agent.anthropic.Anthropic", return_value=mock_client):
        result = ask_agent("Say hi")

    assert result == "Hello there!"
    mock_client.messages.create.assert_called_once_with(
        model="claude-opus-4-8",
        max_tokens=4096,
        messages=[{"role": "user", "content": "Say hi"}],
    )
