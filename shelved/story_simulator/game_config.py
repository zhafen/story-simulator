"""Tunable gameplay/physics constants.

Distinct from `config.py` (infrastructure: file paths, source
identifiers, credential lookup) -- these are numeric defaults that shape
simulation behavior. Currently hardcoded, not authored per-save;
promoting one into an EC-defined `world_config` entity is the natural
next step if a setting ever needs to override one without touching code.
"""

__iacs__ = {"solution of": "story_simulator_mission.tool_catalog.perceive"}

# Perception/visibility geometry: an object subtending less than this
# fraction of the observer's field of view blends into the background.
# A person/door-sized (~2m) object stays perceptible out to roughly 190m
# under these defaults -- see docs/manifest/history.yaml:
# project_history.door_visibility_bug_found_playtesting.
FOV_DEGREES = 60.0
PERCEPTIBLE_FOV_FRACTION = 0.01

# Fallback characteristic size (meters) for an entity with no `size`
# component of its own.
DEFAULT_ENTITY_SIZE = 2.0
