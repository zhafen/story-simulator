from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import ibis
import pytest
from iacs.dataflows import base_etl
from iacs.etl_system import ETLSystem
from iacs.registry import Registry

from story_simulator.systems import (
    AgentSystem,
    ArchivistAgentSystem,
    ETLLoaderSystem,
    InputSystem,
    MapSystem,
    ResolverAgentSystem,
    System,
    VisualizerSystem,
    WORLD_FILE_ID,
    WORLD_YAML_FILENAME,
    _active_aliases,
    _add_input,
    _latest_input,
    _latest_positions,
    _merge_yaml_string,
    _player_position,
)


def _empty_registry() -> Registry:
    return Registry(ibis.duckdb.connect(), {})


def _registry_from_yaml(yaml_text: str) -> Registry:
    """Build a registry the same way the real Systems do: a WORLD_FILE_ID-keyed merge.

    Entity IDs hash `{file_id}:{entity_path}`, so fixtures must use the same
    `WORLD_FILE_ID` key InputSystem/MapSystem/ArchivistAgentSystem merge
    under, or entities created here won't line up with tags/inputs those
    Systems attach later.
    """
    return ETLSystem().execute(base_etl, input_dirs=[], yaml_strings={WORLD_FILE_ID: yaml_text})


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


def _sent_text(mock_client):
    events = mock_client.beta.sessions.events.send.call_args.kwargs["events"]
    return events[0]["content"][0]["text"]


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
    registry = _empty_registry()
    etl = ETLSystem()

    ETLLoaderSystem().step(registry, etl, save_dir, turn=1)

    assert registry.get("origin").count().execute() == 1


def test_etl_loader_system_does_nothing_without_save_dir():
    registry = _empty_registry()
    etl = ETLSystem()

    ETLLoaderSystem().step(registry, etl, None, turn=1)
    # No exception, and nothing to assert against since there's no save_dir.


def test_etl_loader_system_does_not_reload_an_already_loaded_file(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    extra_path = save_dir / "extra.yaml"
    extra_path.write_text("player:\n    - origin\n")
    registry = _empty_registry()
    etl = ETLSystem()
    loader = ETLLoaderSystem()

    loader.step(registry, etl, save_dir, turn=1)
    extra_path.write_text("player:\n    - origin\n    - origin\n")
    loader.step(registry, etl, save_dir, turn=2)

    # Only the first load counted; the on-disk change on turn 2 isn't rescanned.
    assert registry.get("origin").count().execute() == 1


def test_etl_loader_system_loads_a_new_file_discovered_later(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    (save_dir / "extra.yaml").write_text("player:\n    - origin\n")
    registry = _empty_registry()
    etl = ETLSystem()
    loader = ETLLoaderSystem()

    loader.step(registry, etl, save_dir, turn=1)
    (save_dir / "more.yaml").write_text("visitor:\n    - origin\n")
    loader.step(registry, etl, save_dir, turn=2)

    assert registry.get("origin").count().execute() == 2


def test_etl_loader_system_skips_world_yaml(tmp_path):
    save_dir = tmp_path / "save"
    save_dir.mkdir(parents=True)
    (save_dir / WORLD_YAML_FILENAME).write_text("player:\n    - origin\n")
    registry = _empty_registry()
    etl = ETLSystem()

    ETLLoaderSystem().step(registry, etl, save_dir, turn=1)

    # world.yaml is a derived export, never an independent source, so it's
    # never picked up here even on a fresh loader.
    assert "origin" not in registry.component_types


# ---------------------------------------------------------------------------
# InputSystem
# ---------------------------------------------------------------------------


def test_input_system_writes_input_component_on_player_entity(tmp_path):
    save_dir = tmp_path / "save"
    registry = _empty_registry()
    etl = ETLSystem()

    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registry, etl, save_dir, turn=1)

    assert _latest_input(registry, "player", turn=1) == "open the door"


def test_input_system_does_nothing_without_pending_text(tmp_path):
    save_dir = tmp_path / "save"
    registry = _empty_registry()
    etl = ETLSystem()

    InputSystem().step(registry, etl, save_dir, turn=1)

    assert _latest_input(registry, "player", turn=1) is None


def test_input_system_does_nothing_without_save_dir():
    registry = _empty_registry()
    etl = ETLSystem()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registry, etl, None, turn=1)
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
    registry = _empty_registry()
    etl = ETLSystem()

    MapSystem().step(registry, etl, save_dir, turn=1)

    assert _active_aliases(registry) == set()


def test_map_system_tags_entities_within_radius(tmp_path):
    save_dir = tmp_path / "save"
    registry = _registry_from_yaml(_SAMPLE_WORLD_YAML)

    MapSystem(radius=10.0).step(registry, ETLSystem(), save_dir, turn=1)

    assert _active_aliases(registry) == {"nearby_npc"}


def test_map_system_excludes_entities_outside_radius(tmp_path):
    save_dir = tmp_path / "save"
    registry = _registry_from_yaml(_SAMPLE_WORLD_YAML)

    MapSystem(radius=1.0).step(registry, ETLSystem(), save_dir, turn=1)

    assert _active_aliases(registry) == set()


def test_map_system_untags_entities_that_leave_radius(tmp_path):
    save_dir = tmp_path / "save"
    registry = _registry_from_yaml(_SAMPLE_WORLD_YAML)
    etl = ETLSystem()
    MapSystem(radius=10.0).step(registry, etl, save_dir, turn=1)
    assert _active_aliases(registry) == {"nearby_npc"}

    MapSystem(radius=1.0).step(registry, etl, save_dir, turn=2)

    assert _active_aliases(registry) == set()


# ---------------------------------------------------------------------------
# ResolverAgentSystem
# ---------------------------------------------------------------------------


def test_resolver_agent_system_calls_agent_and_records_reply(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    resolver = ResolverAgentSystem()
    registry = _empty_registry()
    etl = ETLSystem()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registry, etl, save_dir, turn=1)

    resolver.step(registry, etl, save_dir, turn=1)

    assert _sent_text(mock_client) == "open the door"
    assert resolver.last_response == "hello back"
    assert _latest_input(registry, "agent", turn=1) == "hello back"


def test_resolver_agent_system_includes_active_entities_in_prompt(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registry = _registry_from_yaml(_SAMPLE_WORLD_YAML)
    etl = ETLSystem()
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    MapSystem(radius=10.0).step(registry, etl, save_dir, turn=1)
    input_system = InputSystem()
    input_system.receive("look around")
    input_system.step(registry, etl, save_dir, turn=1)
    ResolverAgentSystem().step(registry, etl, save_dir, turn=1)

    assert _sent_text(mock_client) == "Active entities nearby: nearby_npc\nPlayer input: look around"


def test_resolver_agent_system_does_nothing_without_command(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

    ResolverAgentSystem().step(_empty_registry(), ETLSystem(), save_dir, turn=1)

    mock_client.beta.sessions.create.assert_not_called()


def test_resolver_agent_system_does_nothing_without_save_dir(monkeypatch):
    mock_client = _make_mock_client("sesn_test123", events=None)
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)
    resolver = ResolverAgentSystem()

    resolver.step(_empty_registry(), ETLSystem(), None, turn=1)

    mock_client.beta.sessions.create.assert_not_called()


# ---------------------------------------------------------------------------
# ArchivistAgentSystem
# ---------------------------------------------------------------------------


def _make_tool_use_block(tool_name, tool_input, block_id):
    block = MagicMock(type="tool_use", input=tool_input, id=block_id)
    block.name = tool_name
    return block


def test_archivist_agent_system_does_nothing_without_narration(tmp_path):
    save_dir = tmp_path / "save"
    registry = _empty_registry()
    etl = ETLSystem()
    input_system = InputSystem()
    input_system.receive("open the door")
    input_system.step(registry, etl, save_dir, turn=1)

    ArchivistAgentSystem().step(registry, etl, save_dir, turn=1)

    # InputSystem no longer touches save_dir at all (it writes straight to
    # the registry), and the Archivist's own LLM tool loop (and the
    # world.yaml export it would trigger) should never have run without a
    # narration to transcribe.
    assert not (save_dir / WORLD_YAML_FILENAME).exists()


def test_archivist_agent_system_dispatches_mcp_and_local_tools(tmp_path, monkeypatch):
    save_dir = tmp_path / "save"
    registry = _empty_registry()
    etl = ETLSystem()
    input_system = InputSystem()
    input_system.receive("I look around")
    input_system.step(registry, etl, save_dir, turn=1)
    _add_input(registry, etl, "player", "you see a door", "agent", 1)

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

    ArchivistAgentSystem().step(registry, etl, save_dir, turn=1)

    assert mcp_calls == [("describe_format", {})]
    assert mock_client.messages.create.call_count == 3
    # The written content was fed straight to ETLSystem and merged in,
    # without rereading save_dir from disk.
    assert registry.get("origin").count().execute() == 1
    # world.yaml is regenerated from the registry afterward (not a verbatim
    # copy of the model's raw tool call), so check its content loosely.
    exported = (save_dir / WORLD_YAML_FILENAME).read_text()
    assert "player" in exported
    assert "origin" in exported


# ---------------------------------------------------------------------------
# Position history (turn-stamped SCD)
# ---------------------------------------------------------------------------


def test_latest_positions_resolves_conflicting_writes_by_turn():
    registry = _empty_registry()
    etl = ETLSystem()
    _merge_yaml_string(
        registry, etl, WORLD_FILE_ID, "player:\n    - position:\n        x: 0.0\n        y: 0.0\n", turn=1
    )
    _merge_yaml_string(
        registry, etl, WORLD_FILE_ID, "player:\n    - position:\n        x: 5.0\n        y: 5.0\n", turn=2
    )

    # Both writes are retained as history, not overwritten...
    assert registry.get("position").count().execute() == 2
    # ...but the higher turn wins when resolving the current position.
    latest = _latest_positions(registry)
    row = latest[latest["entity_id.alias"] == "player"].iloc[0]
    assert (float(row["position.x"]), float(row["position.y"])) == (5.0, 5.0)


def test_player_position_resolves_to_latest_turn():
    registry = _empty_registry()
    etl = ETLSystem()
    _merge_yaml_string(
        registry,
        etl,
        WORLD_FILE_ID,
        "player:\n    - character:\n        interaction_type: player\n    - position:\n        x: 0.0\n        y: 0.0\n",
        turn=1,
    )
    _merge_yaml_string(
        registry, etl, WORLD_FILE_ID, "player:\n    - position:\n        x: 5.0\n        y: 5.0\n", turn=2
    )

    assert _player_position(registry) == ("player", (5.0, 5.0))


def test_archivist_agent_system_stamps_turn_on_position_writes(tmp_path, monkeypatch):
    """A position written on turn 2, with no `turn` in the model's own YAML, wins over turn 1's.

    Regression test for the bug that motivated adding `turn` to `position`:
    the Archivist's freeform YAML never mentions `turn`, so `_merge_yaml_string`
    has to stamp it in automatically for `_latest_positions` to have anything
    to resolve conflicting writes by.
    """
    save_dir = tmp_path / "save"
    registry = _empty_registry()
    etl = ETLSystem()
    final_text = MagicMock(type="text", text="done")

    def _turn_responses(content):
        return [
            MagicMock(content=[_make_tool_use_block("write_world_file", {"content": content}, "tool_write")], stop_reason="tool_use"),
            MagicMock(content=[final_text], stop_reason="end_turn"),
        ]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = (
        _turn_responses("player:\n    - position:\n        x: 0.0\n        y: 0.0\n")
        + _turn_responses("player:\n    - position:\n        x: 5.0\n        y: 5.0\n")
    )
    monkeypatch.setattr("story_simulator.systems.anthropic.Anthropic", lambda **kwargs: mock_client)

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
    input_system.step(registry, etl, save_dir, turn=1)
    _add_input(registry, etl, "player", "you see a clearing", "agent", 1)
    archivist.step(registry, etl, save_dir, turn=1)

    input_system.receive("I walk east")
    input_system.step(registry, etl, save_dir, turn=2)
    _add_input(registry, etl, "player", "you arrive at a river", "agent", 2)
    archivist.step(registry, etl, save_dir, turn=2)

    # Both turns' writes persist as history...
    assert registry.get("position").count().execute() == 2
    # ...but the turn stamped in automatically resolves them to turn 2's value.
    assert _player_position(registry) == ("player", (5.0, 5.0))


# ---------------------------------------------------------------------------
# VisualizerSystem
# ---------------------------------------------------------------------------


def test_visualizer_system_renders_positions(tmp_path):
    save_dir = tmp_path / "save"
    registry = _registry_from_yaml(_SAMPLE_WORLD_YAML)
    render_path = tmp_path / "render.svg"

    VisualizerSystem(render_path=render_path).step(registry, ETLSystem(), save_dir, turn=1)

    assert render_path.exists()
    assert "nearby_npc" in render_path.read_text()


def test_visualizer_system_renders_without_crashing_when_no_positions_exist(tmp_path):
    save_dir = tmp_path / "save"
    render_path = tmp_path / "render.svg"

    VisualizerSystem(render_path=render_path).step(_empty_registry(), ETLSystem(), save_dir, turn=1)

    assert render_path.exists()


def test_visualizer_system_does_nothing_without_save_dir(tmp_path):
    render_path = tmp_path / "render.svg"

    VisualizerSystem(render_path=render_path).step(_empty_registry(), ETLSystem(), None, turn=1)

    assert not render_path.exists()
