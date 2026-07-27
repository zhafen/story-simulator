import json
from unittest.mock import MagicMock

from story_simulator.agents import AgentSpec, complete, run_tool_loop


def _make_tool_call(call_id: str, name: str, arguments: dict):
    function = MagicMock()
    function.name = name
    function.arguments = json.dumps(arguments)
    return MagicMock(id=call_id, function=function)


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


# ---------------------------------------------------------------------------
# AgentSpec.from_yaml
# ---------------------------------------------------------------------------


def test_agent_spec_from_yaml_reads_fields(tmp_path):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        "name: Test Agent\n"
        "description: A test agent.\n"
        "model: claude-haiku-4-5\n"
        "system: Be terse.\n"
        "tools:\n"
        "  - view_registry\n"
    )

    spec = AgentSpec.from_yaml(config_path)

    assert spec.name == "Test Agent"
    assert spec.description == "A test agent."
    assert spec.model == "claude-haiku-4-5"
    assert spec.system == "Be terse."
    assert spec.tools == ["view_registry"]


def test_agent_spec_from_yaml_defaults_tools_to_empty_list(tmp_path):
    config_path = tmp_path / "agent.yaml"
    config_path.write_text("name: Test Agent\nmodel: claude-haiku-4-5\nsystem: Be terse.\n")

    spec = AgentSpec.from_yaml(config_path)

    assert spec.tools == []


def test_agent_spec_from_yaml_inherits_system_from_fallback_when_omitted(tmp_path):
    prod_path = tmp_path / "agent.yaml"
    prod_path.write_text("name: Prod Agent\nmodel: claude-opus-4-8\nsystem: Shared instructions.\n")
    test_path = tmp_path / "agent.test.yaml"
    test_path.write_text("name: Test Agent\nmodel: claude-haiku-4-5\n")

    spec = AgentSpec.from_yaml(test_path, fallback_system_path=prod_path)

    assert spec.system == "Shared instructions."
    assert spec.model == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------


def test_complete_prepends_system_prompt_and_forwards_model(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("hi"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    spec = AgentSpec(name="Test", model="claude-haiku-4-5", system="Be terse.")

    response = complete(spec, [{"role": "user", "content": "hello"}], api_key="test-key")

    assert response.choices[0].message.content == "hi"
    mock_completion.assert_called_once_with(
        model="claude-haiku-4-5",
        messages=[{"role": "system", "content": "Be terse."}, {"role": "user", "content": "hello"}],
        tools=None,
        max_tokens=4096,
        api_key="test-key",
    )


# ---------------------------------------------------------------------------
# run_tool_loop
# ---------------------------------------------------------------------------


def test_run_tool_loop_returns_text_when_no_tool_call_is_made(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("all done"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    spec = AgentSpec(name="Test", model="claude-haiku-4-5", system="Be terse.")

    async def dispatch(name, arguments):
        raise AssertionError("dispatch should never be called")

    import asyncio

    result = asyncio.run(run_tool_loop(spec, [{"role": "user", "content": "go"}], [], dispatch))

    assert result == "all done"
    assert mock_completion.call_count == 1


def test_run_tool_loop_dispatches_tool_calls_and_feeds_results_back(monkeypatch):
    tool_call = _make_tool_call("call_1", "do_thing", {"x": 1})
    mock_completion = MagicMock(
        side_effect=[
            _make_llm_response(None, tool_calls=[tool_call]),
            _make_llm_response("finished"),
        ]
    )
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    spec = AgentSpec(name="Test", model="claude-haiku-4-5", system="Be terse.")

    calls = []

    async def dispatch(name, arguments):
        calls.append((name, arguments))
        return "tool result"

    import asyncio

    result = asyncio.run(run_tool_loop(spec, [{"role": "user", "content": "go"}], [], dispatch))

    assert result == "finished"
    assert calls == [("do_thing", {"x": 1})]
    second_call_messages = mock_completion.call_args_list[1].kwargs["messages"]
    assert {"role": "tool", "tool_call_id": "call_1", "content": "tool result"} in second_call_messages


def test_run_tool_loop_stops_after_max_turns(monkeypatch):
    tool_call = _make_tool_call("call_1", "do_thing", {})
    mock_completion = MagicMock(return_value=_make_llm_response(None, tool_calls=[tool_call]))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    spec = AgentSpec(name="Test", model="claude-haiku-4-5", system="Be terse.")

    async def dispatch(name, arguments):
        return "tool result"

    import asyncio

    result = asyncio.run(
        run_tool_loop(spec, [{"role": "user", "content": "go"}], [], dispatch, max_turns=2)
    )

    # Never converges to a non-tool-call response, so the loop bails out
    # after max_turns rather than looping forever.
    assert result == ""
    assert mock_completion.call_count == 3
