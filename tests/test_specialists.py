from unittest.mock import MagicMock

from story_simulator.specialists import PhysicsAgent, TerrainAgent


def _make_llm_response(content):
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    message.model_dump.return_value = {"role": "assistant", "content": content}
    choice = MagicMock(message=message, finish_reason="stop")
    return MagicMock(choices=[choice])


def test_terrain_agent_generates_from_prod_config(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("Mossy ground, quiet air."))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    result = TerrainAgent().generate("a clearing near the river")

    assert result == "Mossy ground, quiet air."
    sent_messages = mock_completion.call_args.kwargs["messages"]
    assert sent_messages[-1] == {"role": "user", "content": "a clearing near the river"}


def test_physics_agent_resolves_from_prod_config(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("The gap is narrow enough to clear."))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    result = PhysicsAgent().resolve("jumping a two-meter gap")

    assert result == "The gap is narrow enough to clear."
    sent_messages = mock_completion.call_args.kwargs["messages"]
    assert sent_messages[-1] == {"role": "user", "content": "jumping a two-meter gap"}
