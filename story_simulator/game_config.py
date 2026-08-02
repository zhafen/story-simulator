"""Tunable gameplay/physics constants.

Distinct from `config.py`, which is infrastructure (file paths, source
identifiers, credential lookup) -- these are plain numeric defaults that
shape how the simulation behaves, not where its data lives. Every constant
here is currently a hardcoded default, not authored per-save; promoting one
into an EC-defined `world_config` entity (with its schema declared in
`manifest/builtins.yaml`, the way `position.z` already declares a field
default) is the natural next step if a setting ever needs to override one
without touching code.
"""

# Perception/visibility geometry: an object subtending less than this
# fraction of the observer's field of view blends into the background
# rather than staying perceptible. The same heuristic used to place the
# living world's journaling desk (data/living_world/setting.yaml) at a
# distance the original door would no longer be visible from -- and checked
# against real-world visual-acuity/recognition-distance figures
# (docs/architecture.md's door-visibility follow-up): a person/door-sized
# (~2m) object stays perceptible out to roughly 190m under these defaults,
# in the same ballpark as the "a few hundred meters" real-world recognition
# distance research gives for an object that size.
FOV_DEGREES = 60.0
PERCEPTIBLE_FOV_FRACTION = 0.01

# Fallback characteristic size (meters) for an entity with no `size`
# component of its own -- matches the "average door/person height" already
# used as this project's own reference object for the calculation above.
DEFAULT_ENTITY_SIZE = 2.0
