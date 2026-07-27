import asyncio
import itertools
import json
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import matplotlib.pyplot as plt
import pytest
from iacs.registrar import Registrar

from story_simulator.config import MANIFEST_DIR
from story_simulator.systems import (
    AgentSystem,
    ArchivistAgentSystem,
    ETLLoaderSystem,
    InputSystem,
    MapSystem,
    NPCAgentSystem,
    ResolverAgentSystem,
    System,
    VisualizerSystem,
    WORLD_FILE_ID,
    WORLD_YAML_FILENAME,
    _active_aliases,
    _add_input,
    _avoid_overlapping_labels,
    _latest_input,
    _latest_positions,
    _merge_yaml_string,
    _offset_data_point,
    _player_position,
)


def _empty_registrar() -> Registrar:
    return Registrar()


def _registrar_from_yaml(yaml_text: str) -> Registrar:
    """Build a registrar the same way the real Systems do: a WORLD_FILE_ID-keyed merge.

    Entity IDs hash `{file_id}:{entity_path}`, so fixtures must use the same
    `WORLD_FILE_ID` key InputSystem/MapSystem/ArchivistAgentSystem merge
    under, or entities created here won't line up with tags/inputs those
    Systems attach later.
    """
    registrar = Registrar()
    registrar.update(input_dirs=[str(MANIFEST_DIR)], yaml_strings={WORLD_FILE_ID: yaml_text})
    return registrar


def _make_tool_call(call_id: str, name: str, arguments: dict):
    """Build a fake LiteLLM/OpenAI-shaped tool call for a mocked completion response."""
    function = MagicMock()
    function.name = name
    function.arguments = json.dumps(arguments)
    return MagicMock(id=call_id, function=function)


def _make_llm_response(content, tool_calls=None, finish_reason=None):
    """Build a fake LiteLLM `ModelResponse` (OpenAI-shaped: `.choices[0].message`)."""
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


def _sent_text(mock_completion, call_index: int = 0):
    """The `content` of the last message sent on `mock_completion`'s `call_index`-th call."""
    messages = mock_completion.call_args_list[call_index].kwargs["messages"]
    return messages[-1]["content"]


class _FakeMcpSession:
    """Fake iacs MCP session whose view_entity call reports a canned description."""

    tools = []

    async def call_tool(self, name, arguments):
        assert name == "view_entity"
        return f"{arguments['entity_id']} description"


@asynccontextmanager
async def _fake_open_iacs_mcp_session(manifest_dir):
    yield _FakeMcpSession()


def test_system_cannot_be_instantiated():
    with pytest.raises(TypeError):
        System()


def test_agent_system_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AgentSystem()


# ---------------------------------------------------------------------------
# ETLLoaderSystem
# ---------------------------------------------------------------------------


def test_etl_loader_system_loads_pre_existing_save_files(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    (save_dir / "extra.yaml").write_text("player:\n    - origin\n")
    registrar = _empty_registrar()

    ETLLoaderSystem().step(registrar, save_dir, turn=1)

    assert registrar.get("origin").count().execute() == 1


def test_etl_loader_system_does_nothing_without_save_dir():
    registrar = _empty_registrar()

    ETLLoaderSystem().step(registrar, None, turn=1)
    # No exception, and nothing to assert against since there's no save_dir.


def test_etl_loader_system_does_not_reload_an_already_loaded_file(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    extra_path = save_dir / "extra.yaml"
    extra_path.write_text("player:\n    - origin\n")
    registrar = _empty_registrar()
    loader = ETLLoaderSystem()

    loader.step(registrar, save_dir, turn=1)
    extra_path.write_text("player:\n    - origin\n    - origin\n")
    loader.step(registrar, save_dir, turn=2)

    # Only the first load counted; the on-disk change on turn 2 isn't rescanned.
    assert registrar.get("origin").count().execute() == 1


def test_etl_loader_system_loads_a_new_file_discovered_later(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    (save_dir / "extra.yaml").write_text("player:\n    - origin\n")
    registrar = _empty_registrar()
    loader = ETLLoaderSystem()

    loader.step(registrar, save_dir, turn=1)
    (save_dir / "more.yaml").write_text("visitor:\n    - origin\n")
    loader.step(registrar, save_dir, turn=2)

    assert registrar.get("origin").count().execute() == 2


def test_etl_loader_system_skips_world_yaml(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    (save_dir / WORLD_YAML_FILENAME).write_text("player:\n    - origin\n")
    registrar = _empty_registrar()

    ETLLoaderSystem().step(registrar, save_dir, turn=1)

    # world.yaml is a derived export, never an independent source, so it's
    # never picked up here even on a fresh loader.
    assert "origin" not in registrar.registry.component_types


# ---------------------------------------------------------------------------
# InputSystem
# ---------------------------------------------------------------------------


def test_input_system_writes_input_component_on_player_entity(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()

    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registrar, save_dir, turn=1)

    assert _latest_input(registrar, "player", turn=1) == "open the door"


def test_input_system_does_nothing_without_pending_text(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()

    InputSystem().step(registrar, save_dir, turn=1)

    assert _latest_input(registrar, "player", turn=1) is None


def test_input_system_does_nothing_without_save_dir():
    registrar = _empty_registrar()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registrar, None, turn=1)
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


def test_map_system_does_nothing_without_player_data(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()

    MapSystem().step(registrar, save_dir, turn=1)

    assert _active_aliases(registrar) == set()


def test_map_system_tags_entities_within_radius(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)

    MapSystem(radius=10.0).step(registrar, save_dir, turn=1)

    assert _active_aliases(registrar) == {"nearby_npc"}


def test_map_system_excludes_entities_outside_radius(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)

    MapSystem(radius=1.0).step(registrar, save_dir, turn=1)

    assert _active_aliases(registrar) == set()


def test_map_system_untags_entities_that_leave_radius(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    MapSystem(radius=10.0).step(registrar, save_dir, turn=1)
    assert _active_aliases(registrar) == {"nearby_npc"}

    MapSystem(radius=1.0).step(registrar, save_dir, turn=2)

    assert _active_aliases(registrar) == set()


# ---------------------------------------------------------------------------
# NPCAgentSystem
# ---------------------------------------------------------------------------


def test_npc_agent_system_writes_a_command_as_player_type_input(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registrar = _registrar_from_yaml("traveler:\n    - character:\n        interaction_type: npc\n")
    mock_completion = MagicMock(return_value=_make_llm_response("I look around."))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    NPCAgentSystem().step(registrar, save_dir, turn=1)

    assert _latest_input(registrar, "player", turn=1) == "I look around."


def test_npc_agent_system_does_nothing_when_a_command_already_exists(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()
    mock_completion = MagicMock(return_value=_make_llm_response("I look around."))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registrar, save_dir, turn=1)

    NPCAgentSystem().step(registrar, save_dir, turn=1)

    mock_completion.assert_not_called()


# ---------------------------------------------------------------------------
# ResolverAgentSystem
# ---------------------------------------------------------------------------


def test_resolver_agent_system_calls_agent_and_records_reply(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    mock_completion = MagicMock(return_value=_make_llm_response("hello back"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    resolver = ResolverAgentSystem(terrain_agent=MagicMock(), physics_agent=MagicMock())
    registrar = _empty_registrar()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registrar, save_dir, turn=1)

    resolver.step(registrar, save_dir, turn=1)

    # No active entities and no positioned entities at all yet (the seeded
    # "player" entity has no position component), so the prompt reduces to
    # the bare player input, and no iacs MCP session is opened at all.
    assert _sent_text(mock_completion) == "open the door"
    assert resolver.last_response == "hello back"
    assert _latest_input(registrar, "agent", turn=1) == "hello back"


def test_resolver_agent_system_includes_active_entities_in_prompt(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    mock_completion = MagicMock(return_value=_make_llm_response("hello back"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    monkeypatch.setattr("story_simulator.systems.open_iacs_mcp_session", _fake_open_iacs_mcp_session)

    MapSystem(radius=10.0).step(registrar, save_dir, turn=1)
    input_system = InputSystem()
    input_system.receive("look around")
    input_system.step(registrar, save_dir, turn=1)
    ResolverAgentSystem(terrain_agent=MagicMock(), physics_agent=MagicMock()).step(registrar, save_dir, turn=1)

    # Entity details cover every known entity (distant_rock, nearby_npc,
    # player), not just the one tagged active — only the "Active entities
    # nearby" bookkeeping line is radius-limited.
    assert _sent_text(mock_completion) == (
        "Active entities nearby: nearby_npc\n"
        "Entity details:\n"
        "distant_rock description\n"
        "nearby_npc description\n"
        "player description\n"
        "player's input: look around"
    )


def test_resolver_agent_system_does_nothing_without_command(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    mock_completion = MagicMock(return_value=_make_llm_response("hello back"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    ResolverAgentSystem(terrain_agent=MagicMock(), physics_agent=MagicMock()).step(
        _empty_registrar(), save_dir, turn=1
    )

    mock_completion.assert_not_called()


def test_resolver_agent_system_does_nothing_without_save_dir(monkeypatch):
    mock_completion = MagicMock(return_value=_make_llm_response("hello back"))
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)
    resolver = ResolverAgentSystem(terrain_agent=MagicMock(), physics_agent=MagicMock())

    resolver.step(_empty_registrar(), None, turn=1)

    mock_completion.assert_not_called()


def test_resolver_agent_system_calls_generate_terrain_tool(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    tool_call = _make_tool_call("call_1", "generate_terrain", {"description": "a clearing"})
    mock_completion = MagicMock(
        side_effect=[
            _make_llm_response(None, tool_calls=[tool_call]),
            _make_llm_response("You see a mossy clearing."),
        ]
    )
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    fake_terrain = MagicMock()
    fake_terrain.generate.return_value = "Mossy ground, quiet air."
    resolver = ResolverAgentSystem(terrain_agent=fake_terrain, physics_agent=MagicMock())
    registrar = _empty_registrar()
    input_system = InputSystem()
    input_system.receive("look around")
    input_system.step(registrar, save_dir, turn=1)

    resolver.step(registrar, save_dir, turn=1)

    fake_terrain.generate.assert_called_once_with("a clearing")
    assert resolver.last_response == "You see a mossy clearing."
    # The specialist's result round-trips into the next turn sent to the model.
    second_call_messages = mock_completion.call_args_list[1].kwargs["messages"]
    assert {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "Mossy ground, quiet air.",
    } in second_call_messages


def test_resolver_agent_system_calls_resolve_physics_tool(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    tool_call = _make_tool_call("call_1", "resolve_physics", {"scenario": "jumping a gap"})
    mock_completion = MagicMock(
        side_effect=[
            _make_llm_response(None, tool_calls=[tool_call]),
            _make_llm_response("You clear the gap easily."),
        ]
    )
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    fake_physics = MagicMock()
    fake_physics.resolve.return_value = "The gap is narrow enough to clear."
    resolver = ResolverAgentSystem(terrain_agent=MagicMock(), physics_agent=fake_physics)
    registrar = _empty_registrar()
    input_system = InputSystem()
    input_system.receive("I jump the gap")
    input_system.step(registrar, save_dir, turn=1)

    resolver.step(registrar, save_dir, turn=1)

    fake_physics.resolve.assert_called_once_with("jumping a gap")
    assert resolver.last_response == "You clear the gap easily."


# ---------------------------------------------------------------------------
# ArchivistAgentSystem
# ---------------------------------------------------------------------------


def test_archivist_agent_system_does_nothing_without_narration(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registrar, save_dir, turn=1)
    mock_completion = MagicMock()
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    ArchivistAgentSystem().step(registrar, save_dir, turn=1)

    # The Archivist's own LLM tool loop should never have run without a
    # narration to transcribe.
    mock_completion.assert_not_called()


def test_archivist_agent_system_dispatches_mcp_and_local_tools(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()
    input_system = InputSystem()
    input_system.receive("I look around")
    input_system.step(registrar, save_dir, turn=1)
    _add_input(registrar, "player", "you see a door", "agent", 1)

    describe_call = _make_tool_call("tool_1", "describe_format", {})
    update_call = _make_tool_call(
        "tool_2", "update_registry", {"yaml_string": "player:\n    - origin\n"}
    )

    mock_completion = MagicMock(
        side_effect=[
            _make_llm_response(None, tool_calls=[describe_call]),
            _make_llm_response(None, tool_calls=[update_call]),
            _make_llm_response("done"),
        ]
    )
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    mcp_calls = []

    class FakeMcpSession:
        tools = [
            {"type": "function", "function": {"name": "describe_format", "description": "", "parameters": {}}}
        ]

        async def call_tool(self, name, arguments):
            mcp_calls.append((name, arguments))
            return "format guide text"

    @asynccontextmanager
    async def fake_open_iacs_mcp_session(manifest_dir):
        yield FakeMcpSession()

    monkeypatch.setattr(
        "story_simulator.systems.open_iacs_mcp_session", fake_open_iacs_mcp_session
    )

    ArchivistAgentSystem().step(registrar, save_dir, turn=1)

    assert mcp_calls == [("describe_format", {})]
    assert mock_completion.call_count == 3
    # `update_registry` fed the YAML straight to Registrar.update and merged
    # it into the registry directly, with no on-disk save file involved.
    assert registrar.get("origin").count().execute() == 1
    assert not (save_dir / WORLD_YAML_FILENAME).exists()


def test_dispatch_tool_view_registry_reads_a_component_type():
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    archivist = ArchivistAgentSystem()

    result = asyncio.run(
        archivist._dispatch_tool(None, registrar, 1, "view_registry", {"component_type": "position"})
    )

    assert "distant_rock" in result
    assert "nearby_npc" in result


def test_dispatch_tool_reports_errors_without_crashing_the_turn():
    """An unknown component_type (a plausible model typo/hallucination) shouldn't crash the turn.

    `_dispatch_tool` has no MCP server underneath it translating exceptions
    into tool results the way FastMCP does for its own tools, so it has to
    do that translation itself.
    """
    registrar = _empty_registrar()
    archivist = ArchivistAgentSystem()

    result = asyncio.run(
        archivist._dispatch_tool(None, registrar, 1, "view_registry", {"component_type": "nonexistent"})
    )

    assert "Error" in result


def test_dispatch_tool_update_registry_merges_valid_yaml():
    registrar = _empty_registrar()
    archivist = ArchivistAgentSystem()

    result = asyncio.run(
        archivist._dispatch_tool(
            None, registrar, 1, "update_registry", {"yaml_string": "player:\n    - origin\n"}
        )
    )

    assert "Merged" in result
    assert registrar.get("origin").count().execute() == 1


def test_dispatch_tool_update_registry_reports_malformed_yaml_without_crashing_the_turn():
    registrar = _empty_registrar()
    archivist = ArchivistAgentSystem()

    result = asyncio.run(
        archivist._dispatch_tool(
            None, registrar, 1, "update_registry", {"yaml_string": "player:\n  - foo: [unterminated"}
        )
    )

    assert "Error" in result
    assert "origin" not in registrar.registry.component_types


# ---------------------------------------------------------------------------
# Position history (turn-stamped SCD)
# ---------------------------------------------------------------------------


def test_latest_positions_resolves_conflicting_writes_by_turn():
    registrar = _empty_registrar()
    _merge_yaml_string(
        registrar, WORLD_FILE_ID, "player:\n    - position:\n        x: 0.0\n        y: 0.0\n", turn=1
    )
    _merge_yaml_string(
        registrar, WORLD_FILE_ID, "player:\n    - position:\n        x: 5.0\n        y: 5.0\n", turn=2
    )

    # Both writes are retained as history, not overwritten...
    assert registrar.get("position").count().execute() == 2
    # ...but the higher turn wins when resolving the current position.
    latest = _latest_positions(registrar)
    row = latest[latest["entity_id.alias"] == "player"].iloc[0]
    assert (float(row["position.x"]), float(row["position.y"])) == (5.0, 5.0)


def test_player_position_resolves_to_latest_turn():
    registrar = _empty_registrar()
    _merge_yaml_string(
        registrar,
        WORLD_FILE_ID,
        "player:\n    - character:\n        interaction_type: player\n    - position:\n        x: 0.0\n        y: 0.0\n",
        turn=1,
    )
    _merge_yaml_string(
        registrar, WORLD_FILE_ID, "player:\n    - position:\n        x: 5.0\n        y: 5.0\n", turn=2
    )

    assert _player_position(registrar) == ("player", (5.0, 5.0))


def test_archivist_agent_system_stamps_turn_on_position_writes(tmp_path, monkeypatch):
    """A position written on turn 2, with no `turn` in the model's own YAML, wins over turn 1's.

    Regression test for the bug that motivated adding `turn` to `position`:
    the Archivist's freeform YAML never mentions `turn`, so `_merge_yaml_string`
    has to stamp it in automatically for `_latest_positions` to have anything
    to resolve conflicting writes by.
    """
    save_dir = tmp_path / "save"
    registrar = _empty_registrar()

    def _turn_responses(content):
        tool_call = _make_tool_call("tool_update", "update_registry", {"yaml_string": content})
        return [
            _make_llm_response(None, tool_calls=[tool_call]),
            _make_llm_response("done"),
        ]

    mock_completion = MagicMock(
        side_effect=(
            _turn_responses("player:\n    - position:\n        x: 0.0\n        y: 0.0\n")
            + _turn_responses("player:\n    - position:\n        x: 5.0\n        y: 5.0\n")
        )
    )
    monkeypatch.setattr("story_simulator.agents.litellm.completion", mock_completion)

    class FakeMcpSession:
        tools = []

        async def call_tool(self, name, arguments):
            raise AssertionError("no MCP tools expected in this test")

    @asynccontextmanager
    async def fake_open_iacs_mcp_session(manifest_dir):
        yield FakeMcpSession()

    monkeypatch.setattr("story_simulator.systems.open_iacs_mcp_session", fake_open_iacs_mcp_session)

    archivist = ArchivistAgentSystem()
    input_system = InputSystem()

    input_system.receive("I look around")
    input_system.step(registrar, save_dir, turn=1)
    _add_input(registrar, "player", "you see a clearing", "agent", 1)
    archivist.step(registrar, save_dir, turn=1)

    input_system.receive("I walk east")
    input_system.step(registrar, save_dir, turn=2)
    _add_input(registrar, "player", "you arrive at a river", "agent", 2)
    archivist.step(registrar, save_dir, turn=2)

    # Both turns' writes persist as history...
    assert registrar.get("position").count().execute() == 2
    # ...but the turn stamped in automatically resolves them to turn 2's value.
    assert _player_position(registrar) == ("player", (5.0, 5.0))


# ---------------------------------------------------------------------------
# VisualizerSystem
# ---------------------------------------------------------------------------


def test_visualizer_system_renders_positions(tmp_path):
    save_dir = tmp_path / "save"
    registrar = _registrar_from_yaml(_SAMPLE_WORLD_YAML)
    render_path = tmp_path / "render.svg"

    VisualizerSystem(render_path=render_path).step(registrar, save_dir, turn=1)

    assert render_path.exists()
    assert "nearby_npc" in render_path.read_text()


def test_visualizer_system_renders_without_crashing_when_no_positions_exist(tmp_path):
    save_dir = tmp_path / "save"
    render_path = tmp_path / "render.svg"

    VisualizerSystem(render_path=render_path).step(_empty_registrar(), save_dir, turn=1)

    assert render_path.exists()


def test_visualizer_system_does_nothing_without_save_dir(tmp_path):
    render_path = tmp_path / "render.svg"

    VisualizerSystem(render_path=render_path).step(_empty_registrar(), None, turn=1)

    assert not render_path.exists()


def _label_boxes(annotations):
    fig = annotations[0].figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    return [annotation.get_window_extent(renderer) for annotation in annotations]


def _has_overlap(boxes):
    for bi, bj in itertools.combinations(boxes, 2):
        overlap_x = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
        overlap_y = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
        if overlap_x > 0 and overlap_y > 0:
            return True
    return False


def test_avoid_overlapping_labels_separates_clustered_labels():
    fig, ax = plt.subplots()
    points = [(0.0, 0.0), (0.01, 0.01), (0.02, -0.01), (0.0, 0.02)]
    ax.scatter([p[0] for p in points], [p[1] for p in points])
    annotations = [
        ax.annotate(
            alias,
            xy=xy,
            xytext=_offset_data_point(ax, xy, 5, 5),
            textcoords="data",
            arrowprops=dict(arrowstyle="-"),
        )
        for xy, alias in zip(points, ["alice_the_brave", "bob", "a_very_long_alias", "sir_charles"])
    ]
    assert _has_overlap(_label_boxes(annotations))

    _avoid_overlapping_labels(fig, ax, annotations)

    assert not _has_overlap(_label_boxes(annotations))
    plt.close(fig)


def test_avoid_overlapping_labels_leaves_far_apart_labels_untouched():
    fig, ax = plt.subplots()
    points = [(0.0, 0.0), (100.0, 100.0)]
    ax.scatter([p[0] for p in points], [p[1] for p in points])
    annotations = [
        ax.annotate(
            alias,
            xy=xy,
            xytext=_offset_data_point(ax, xy, 5, 5),
            textcoords="data",
            arrowprops=dict(arrowstyle="-"),
        )
        for xy, alias in zip(points, ["alice", "bob"])
    ]
    original_positions = [annotation.xyann for annotation in annotations]

    _avoid_overlapping_labels(fig, ax, annotations)

    assert [annotation.xyann for annotation in annotations] == original_positions
    plt.close(fig)
