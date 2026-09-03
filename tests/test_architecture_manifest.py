"""Tests for docs/manifest/story-simulator.yaml -- the project's own
architecture manifest (requirements/solutions/dependencies), not the
gameplay data in manifest/builtins.yaml. Loads the same way iacs's
scripts/generate_requirement_tree_report.py does, so a typo or broken
`dependence of:`/`solution of:` link in the manifest fails a fast test
instead of only surfacing as a silently-empty report section.
"""

import pytest

from emc2p.dataflows.derive.resolve_paths import (
    components_with_resolved_paths,
    fields_of_type_entity_ref,
    implicit_parent_target_types,
    parent_from_hierarchy,
)
from emc2p.registrar import Registrar

NEW_TREE_ENTITY_KEY = "human_validated_test_framework"
DEPENDENCIES_KEY = "dependencies"
MANIFEST_PATHS = ["docs/manifest", "story_simulator"]

# Every test here loads a real manifest via Registrar.from_manifest -- the
# Hamilton driver construction that goes through dominates regardless of
# manifest size (see pyproject.toml's own `slow` marker docstring).
pytestmark = pytest.mark.slow


def _resolved_components(registrar: Registrar) -> dict:
    entity_id = registrar.get("entity_id")
    field = registrar.get("field")
    hierarchy = parent_from_hierarchy(entity_id)
    components = registrar._registry._components
    return components_with_resolved_paths(
        entity_id=entity_id,
        components=components,
        fields_of_type_entity_ref=fields_of_type_entity_ref(entity_id, field),
        parent_from_hierarchy=hierarchy,
        implicit_parent_target_types=implicit_parent_target_types(components),
    )


def test_architecture_manifest_loads():
    registrar = Registrar.from_manifest(MANIFEST_PATHS)
    assert "requirement" in registrar.registry.component_types
    assert "solution" in registrar.registry.component_types


class TestHumanValidatedTestFrameworkDependencies:
    """The dependencies: subtree under human_validated_test_framework --
    six implementation entities, linked from selected solutions via
    `dependence of:` relations (see docs/manifest/story-simulator.yaml)."""

    def _dependency_paths(self, registrar):
        eids = registrar.get("entity_id").execute()
        path_of = dict(zip(eids["value"].astype(str), eids["path"].astype(str)))
        marker = f".{NEW_TREE_ENTITY_KEY}.{DEPENDENCIES_KEY}."
        return {
            eid: p.split(":", 1)[1]
            for eid, p in path_of.items()
            if marker in p.split(":", 1)[1]
        }

    def test_every_dependence_relation_resolves(self):
        """No dangling `dependence of:` target -- every link a selected
        solution makes to a dependencies: entity must actually resolve to
        that entity, not silently stay null (e.g. from a typo'd name)."""
        registrar = Registrar.from_manifest(MANIFEST_PATHS)
        resolved = _resolved_components(registrar)
        dep_df = resolved["dependence"].to_pandas()
        assert len(dep_df) > 0, "expected at least one dependence relation in the manifest"
        unresolved = dep_df[dep_df["value_eid"].isna()]
        assert unresolved.empty, (
            f"{len(unresolved)} dependence relation(s) failed to resolve: "
            f"{unresolved['entity_id'].tolist()}"
        )

    def test_every_dependence_target_is_inside_the_dependencies_subtree(self):
        """A dependence relation should only ever point at an entity under
        .../dependencies/, never somewhere else by mistake."""
        registrar = Registrar.from_manifest(MANIFEST_PATHS)
        resolved = _resolved_components(registrar)
        dep_df = resolved["dependence"].to_pandas()
        dependency_ids = set(self._dependency_paths(registrar))
        for target in dep_df["value_eid"].dropna():
            assert str(target) in dependency_ids

    def test_every_dependency_entity_has_a_location_and_work_state(self):
        """Each dependencies: entity should carry both fields the report's
        Dependencies section renders -- location (the real qualified
        path/module/fixture name) and work_state."""
        registrar = Registrar.from_manifest(MANIFEST_PATHS)
        dependency_ids = set(self._dependency_paths(registrar))
        assert len(dependency_ids) == 4

        location_ids = set(registrar.get("location").execute()["entity_id"].astype(str))
        work_state_ids = set(registrar.get("work_state").execute()["entity_id"].astype(str))
        missing_location = dependency_ids - location_ids
        missing_work_state = dependency_ids - work_state_ids
        assert not missing_location, f"missing location: {missing_location}"
        assert not missing_work_state, f"missing work_state: {missing_work_state}"
