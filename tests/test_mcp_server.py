import emc2p.mcp_server as emc2p_mcp_server
import pytest

from conftest import _make_ctx
from story_simulator.config import LIVING_WORLD_DIR
from story_simulator.core import _get_registrar, _registrars, _save_dirs
from story_simulator.mcp_server import (
    server,
    start_world,
    update_registry,
    view_entity,
    view_registry,
)


# MCP tool registration smoke tests


class TestMcpToolRegistration:
    def _tool_names(self):
        return {t.name for t in server._tool_manager.list_tools()}

    def test_all_tools_are_registered(self):
        expected = {
            "start_world",
            "view_registry",
            "view_entity",
            "update_registry",
            "advance_simulation",
        }
        assert expected <= self._tool_names()
        # perceive/generate_terrain/resolve_physics/advance_npc_turn moved
        # out to shelved/ along with the rest of the optional-module code.
        assert not {"perceive", "generate_terrain", "resolve_physics", "advance_npc_turn"} & self._tool_names()

    def test_open_registry_is_not_mounted(self):
        """start_world already covers opening/tracking the world registrar
        -- mounting emc2p's own open_registry too would let a client
        silently swap it out for an unrelated one mid-session."""
        assert "open_registry" not in self._tool_names()

    def test_view_registry_and_view_entity_are_emc2p_s_own_tools(self):
        """Mounted directly from emc2p.mcp_server, not reimplemented here."""
        assert view_registry is emc2p_mcp_server.view_registry
        assert view_entity is emc2p_mcp_server.view_entity

    def test_update_registry_keeps_this_server_s_own_richer_version(self):
        """emc2p's own update_registry lacks the preview/confirm_token flow
        and save_dir export sync -- the mounting loop must not let it win
        the name collision."""
        assert update_registry is not emc2p_mcp_server.update_registry


# start_world


class TestStartWorld:
    def test_returns_confirmation_string(self, tmp_path):
        ctx = _make_ctx()
        result = start_world(str(tmp_path / "save"), ctx)
        assert "World opened" in result

    def test_seeds_from_default_world_by_default(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert "origin" in registrar.registry.component_types

    def test_seeds_from_given_scenario_dir(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx, scenario_dir=str(LIVING_WORLD_DIR))
        registrar = _registrars[ctx.request_context.session]
        positions = registrar.view_df("position")
        assert "journaling_desk.journal" in positions["entity_id.alias"].values

    def test_stores_registrar_and_save_dir_for_session(self, tmp_path):
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx)
        assert ctx.request_context.session in _registrars
        assert _save_dirs[ctx.request_context.session] == save_dir

    def test_does_not_reseed_an_already_populated_save_dir(self, tmp_path):
        save_dir = tmp_path / "save"
        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        update_registry("custom_entity:\n    - origin\n", ctx=ctx)

        ctx2 = _make_ctx()
        start_world(str(save_dir), ctx2)
        registrar = _registrars[ctx2.request_context.session]
        assert registrar.get("origin").count().execute() == 2  # world's + custom_entity's

    def test_first_open_loads_only_world_history_dir_when_present(self, tmp_path):
        """world_history/, world/, and the seed are all redundant with each
        other -- loading more than one at once risks silently discarding data.

        (YAML's last-key-wins on duplicate top-level keys replaces
        rather than merges.) world_history/ is the fullest, so it wins
        alone. Each directory can hold more than one yaml file (a
        save's author is free to split it up), so the loader must
        recurse into whichever it picks.
        """
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        (save_dir / "scenario.yaml").write_text("seed_only:\n    - origin\n")
        (save_dir / "world").mkdir()
        (save_dir / "world" / "world.yaml").write_text("world_only:\n    - origin\n")
        (save_dir / "world_history").mkdir()
        (save_dir / "world_history" / "a.yaml").write_text("history_a:\n    - origin\n")
        (save_dir / "world_history" / "nested").mkdir()
        (save_dir / "world_history" / "nested" / "b.yaml").write_text(
            "history_b:\n    - origin\n"
        )

        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("history_a") is not None
        assert registrar.get_entity_id("history_b") is not None
        assert registrar.get_entity_id("world_only") is None
        assert registrar.get_entity_id("seed_only") is None

    def test_first_open_loads_only_world_dir_when_no_history_dir(self, tmp_path):
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        (save_dir / "scenario.yaml").write_text("seed_only:\n    - origin\n")
        (save_dir / "world").mkdir()
        (save_dir / "world" / "world.yaml").write_text("world_only:\n    - origin\n")

        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("world_only") is not None
        assert registrar.get_entity_id("seed_only") is None

    def test_first_open_falls_back_to_recursive_glob_when_neither_dir_exists(self, tmp_path):
        """A pristine, never-yet-exported scenario_dir may be organized
        across several files at arbitrary depth -- everything under save_dir should still load."""
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        (save_dir / "scenario.yaml").write_text("seed_a:\n    - origin\n")
        (save_dir / "locations").mkdir()
        (save_dir / "locations" / "field.yaml").write_text("seed_b:\n    - origin\n")

        ctx = _make_ctx()
        start_world(str(save_dir), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("seed_a") is not None
        assert registrar.get_entity_id("seed_b") is not None


# view_registry / view_entity / update_registry


class TestRegistryTools:
    def test_get_registrar_errors_before_start_world(self):
        ctx = _make_ctx()
        with pytest.raises(ValueError, match="start_world"):
            _get_registrar(ctx.request_context.session)

    def test_view_registry_before_start_world_names_start_world_not_open_registry(self):
        """view_registry is emc2p's own function, but wired to this
        server's own _get_registrar (see mcp_server.py's module docstring)
        -- the error it raises must point at start_world, the tool this
        server actually has, not emc2p's own open_registry (not mounted here)."""
        ctx = _make_ctx()
        with pytest.raises(ValueError, match="start_world") as exc_info:
            view_registry("position", ctx)
        assert "open_registry" not in str(exc_info.value)

    def test_view_registry_returns_markdown_table_of_positions(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = view_registry("position", ctx)
        assert "player" in result

    def test_view_registry_delegates_to_iacs_registrar_view_df(self, tmp_path):
        """Not a reimplementation -- the same Registrar.view_df call
        iacs's own view_component tool wraps too."""
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert view_registry("position", ctx) == registrar.view_df("position").fillna("null").to_markdown()

    def test_update_registry_merges_new_entity(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = update_registry("new_thing:\n    - origin\n", ctx=ctx)
        assert "Merged" in result
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get("origin").count().execute() == 2

    def test_update_registry_rejects_bare_mapping_components(self, tmp_path):
        """A component written without the required leading `- ` (a bare
        mapping instead of a list) is silently ignored by iacs's own ETL.

        No error, no invalid_field row, no data merged. Confirmed live
        as a real failure mode (a responder's write appeared to succeed
        but left the registry untouched), so update_registry now
        raises instead of reporting success for it.
        """
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        with pytest.raises(ValueError, match="car_a"):
            update_registry("car_a:\n    state: parked on street\n", ctx=ctx)
        registrar = _registrars[ctx.request_context.session]
        assert "state" not in registrar.registry.component_types

    def test_update_registry_rejects_invented_component_type(self, tmp_path):
        """The recurring live-test bug this mechanically backstops: a weak
        model invents a plausible name (parked_at) instead of the real, declared one (location)."""
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        with pytest.raises(ValueError, match="parked_at"):
            update_registry("car_a:\n    - parked_at: parking_spot_1\n", ctx=ctx)
        registrar = _registrars[ctx.request_context.session]
        assert "parked_at" not in registrar.registry.component_types

    def test_update_registry_suggests_close_match_for_typo(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        with pytest.raises(ValueError, match="locaton.*location"):
            update_registry("car_a:\n    - locaton: parked on street\n", ctx=ctx)

    def test_update_registry_allows_declared_but_previously_unused_component_type(self, tmp_path):
        """A real component type nothing has written to yet (declared in
        manifest/builtins.yaml, e.g. `location`) must not be rejected as unknown.

        component_types alone only reflects data-bearing types, which
        is exactly the gap that let this bug go unnoticed in the first
        place (see iacs's own known_component_types).
        """
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = update_registry("car_a:\n    - location:\n        value: parked on street\n", ctx=ctx)
        assert "Merged" in result

    def test_update_registry_allows_unknown_type_defined_in_the_same_write(self, tmp_path):
        """Overriding the check is allowed, but only by actually defining the
        new component type inline -- the same shape builtins.yaml's own definitions use."""
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = update_registry(
            "brand_new_component:\n"
            "    - description: A freshly-declared component type.\n"
            "    - component_type\n"
            "    - field:\n"
            "        value:\n"
            "            description: Its one field.\n"
            "            type: str\n"
            "\n"
            "car_a:\n"
            "    - brand_new_component:\n"
            "        value: hello\n",
            ctx=ctx,
        )
        assert "Merged" in result

    def test_update_registry_accepts_legitimate_nested_entities(self, tmp_path):
        """A dict value isn't always the bare-mapping mistake.

        A nested entity (each sub-key its own child entity, e.g.
        tests/data/scenarios/move/scenario.yaml's journaling_desk) is
        a dict too, and must still be accepted.
        """
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = update_registry(
            "desk:\n"
            "    data:\n"
            "        - note: just documentation, never its own entity\n"
            "    journal:\n"
            "        - object:\n"
            "            type: journal\n",
            ctx=ctx,
        )
        assert "Merged" in result
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("desk.journal") is not None

    def test_update_registry_rejects_component_name_used_as_nested_entity_key(self, tmp_path):
        """The live-test bug this backstops: a component name used as a
        nested dict key (missing the leading `- ` that would make it a list item).

        Parses as "car_b has a nested child entity named location",
        not "attach a location component to car_b" -- structurally
        identical to
        test_update_registry_accepts_legitimate_nested_entities'
        genuine nesting, distinguished only by `location` being a
        real, already-declared component type.
        """
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        with pytest.raises(ValueError, match="location"):
            update_registry("car_b:\n    location:\n        - value: parked in parking_spot_1\n", ctx=ctx)
        registrar = _registrars[ctx.request_context.session]
        assert registrar.get_entity_id("car_b.location") is None

    def test_update_registry_accepts_correct_list_form_for_known_component(self, tmp_path):
        """Sanity check alongside the rejection above: the correct list
        form for the same component (`location` as a list item) must not be caught by the new check."""
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = update_registry(
            "car_b:\n"
            "    - object:\n"
            "        type: car\n"
            "    - location:\n"
            "        value: parked in parking_spot_1\n",
            ctx=ctx,
        )
        assert "Merged" in result

    def test_update_registry_writes_collapsed_and_full_history_yaml(self, tmp_path):
        ctx = _make_ctx()
        save_dir = tmp_path / "save"
        start_world(str(save_dir), ctx)
        update_registry("door:\n    - description: first\n", ctx=ctx)
        update_registry("door:\n    - description: second\n", ctx=ctx)

        world_text = (save_dir / "world" / "world.yaml").read_text()
        assert "second" in world_text
        assert "first" not in world_text

        history_text = (save_dir / "world_history" / "world.yaml").read_text()
        assert "second" in history_text
        assert "first" in history_text

    def test_view_entity_returns_known_component_data(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = view_entity("player", ctx)
        assert "character" in result

    def test_view_entity_reports_unknown_entity(self, tmp_path):
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        result = view_entity("nonexistent_xyz", ctx)
        assert "No data found" in result

    def test_view_entity_delegates_to_iacs_registrar_view_entity(self, tmp_path):
        """Not a reimplementation -- the same Registrar.view_entity call
        iacs's own view_entity tool wraps too."""
        ctx = _make_ctx()
        start_world(str(tmp_path / "save"), ctx)
        registrar = _registrars[ctx.request_context.session]
        assert view_entity("player", ctx) == registrar.view_entity("player", format="markdown")
