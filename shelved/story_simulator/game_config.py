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

# Coefficient of restitution used by story_simulator.collision.resolve_collision
# when resolve_interaction (story_simulator/interaction.py) works out a
# surviving collision's post-impact velocities -- 1.0 is perfectly elastic
# (no kinetic energy lost), 0.0 is perfectly inelastic (objects move
# together afterward). 0.9 is a gameplay default (most interactions stay
# lively, but every hit an object survives still measurably erodes its
# binding energy via the lost energy), not a measured material property.
DEFAULT_COEFFICIENT_OF_RESTITUTION = 0.9
