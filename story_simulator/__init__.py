"""story-simulator: a text-simulation game master built on top of emc2p's
generic Entity-Component System engine.

Registers this package's own manifest directory with emc2p's
register_builtins_dir extension point (the same mechanism iacs uses for
its own builtins/), so every manifest load -- start_world's own
registrar.update() call, but also any ad hoc Registrar()/from_manifest()
inspection elsewhere (a notebook, a script) -- always picks up
story-simulator's own component-type declarations (character, state,
position, event, ...) alongside emc2p's generic ones (entity_id,
description, ...), regardless of what input_dirs/manifest that particular
call happens to pass.
"""
from emc2p.dataflows.etl.load_manifest import register_builtins_dir

from .config import MANIFEST_DIR

register_builtins_dir(MANIFEST_DIR, "story_simulator_builtins")
