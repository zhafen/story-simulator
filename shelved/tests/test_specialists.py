from unittest.mock import MagicMock

from story_simulator.specialists import PhysicsAgent, TerrainAgent


def _make_llm_response(content):
    """Build a fake LiteLLM `ModelResponse` (OpenAI-shaped) with no tool calls.

    Both specialists only ever make a single plain completion call (see
    TerrainAgent.generate/PhysicsAgent.resolve), so this doesn't need the
    tool_calls handling test_systems.py's/test_agents.py's versions have.
    """
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


def test_estimate_quantity_parses_a_bare_number(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("42.5"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    result = PhysicsAgent().estimate_quantity("a thrown rock", "mass", "kilograms", "a rock is thrown")

    assert result == 42.5


def test_estimate_quantity_tolerates_surrounding_text(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("Approximately 1200 Joules."))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    result = PhysicsAgent().estimate_quantity(
        "a sprinting NPC", "kinetic energy", "Joules", "an NPC sprints toward a door"
    )

    assert result == 1200.0


def test_estimate_collision_velocities_parses_two_vectors(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("3.0, 0.0, 0.0\n-2.5, 1.0, 0.0"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    velocity_a, velocity_b = PhysicsAgent().estimate_collision_velocities(
        "a thrown rock", "a window", "a rock is thrown at a window"
    )

    assert velocity_a == (3.0, 0.0, 0.0)
    assert velocity_b == (-2.5, 1.0, 0.0)


def test_identify_interacting_pairs_skips_the_model_for_two_entities():
    mock_completion = MagicMock()

    pairs = PhysicsAgent().identify_interacting_pairs(["rock", "window"], "a rock hits a window")

    assert pairs == [("rock", "window")]
    mock_completion.assert_not_called()


def test_identify_interacting_pairs_skips_the_model_for_fewer_than_two_entities():
    assert PhysicsAgent().identify_interacting_pairs(["rock"], "a rock falls") == []
    assert PhysicsAgent().identify_interacting_pairs([], "nothing happens") == []


def test_identify_interacting_pairs_parses_multiple_ordered_pairs(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("rock, window\nrock, table"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    pairs = PhysicsAgent().identify_interacting_pairs(
        ["rock", "window", "table", "bystander"], "a rock is thrown across the room"
    )

    assert pairs == [("rock", "window"), ("rock", "table")]
