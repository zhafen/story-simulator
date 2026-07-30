"""Shared configuration: file paths, source identifiers, and credential lookup.

Every other story_simulator module imports from here rather than
hardcoding these paths/constants itself, so there's one place that knows
where the manifest, save-data seeds, and world-registry source key live.
"""

import os
from pathlib import Path

# The source identifier every direct registrar update (story_simulator.mcp_server,
# story_simulator.spatial) merges under. Shared here so every module writing
# to the registry uses the same key without depending on each other.
WORLD_FILE_ID = "world"

# The story-simulator's own component/field schema (position, character, ...).
# Every base_etl call needs this in `input_dirs` for its component types to
# be schema-validated — without it, validate_components has no field
# definitions for them and passes their data through unvalidated/untyped.
MANIFEST_DIR = Path(__file__).parent.parent / "manifest"

# The tracked, ever-growing "living world" save data — a `settings_dir` a
# caller can pass to `start_world` instead of the plain default. Its
# setting.yaml carries a door mechanic that teleports the player forward in
# time and further from the origin each time they walk through it (see
# data/living_world/setting.yaml), and its own directory accumulates history
# turn over turn as it's played, unlike a fresh save_dir seeded from
# DEFAULT_WORLD_DIR.
LIVING_WORLD_DIR = Path(__file__).parent.parent / "data" / "living_world"

# A plain, hand-authored starting scenario (the player, a door, an empty
# expanse) with none of the living world's teleport/history mechanic. This is
# what `start_world` seeds a save_dir from when no `settings_dir` is given,
# so an ordinary throwaway save always starts from the same simple premise
# rather than wherever the living world currently stands.
DEFAULT_WORLD_DIR = Path(__file__).parent.parent / "data" / "default"


def resolve_anthropic_api_key() -> str | None:
    """Read the Anthropic API key from its app-specific env var.

    Some hosting environments reserve ANTHROPIC_API_KEY for their own
    credential plumbing and strip user-supplied values under that name, so
    the key is read from STORY_SIM_ANTHROPIC_API_KEY here. Every agent
    (`story_simulator.agents.complete`/`run_tool_loop`) passes this
    explicitly as `api_key=`. Returning None falls back to each SDK/LiteLLM's
    own ANTHROPIC_API_KEY auto-discovery, which still works for local
    development.

    Only covers Anthropic-flavored `model:` strings (still every agent's
    default today). An agent configured for another provider relies on
    LiteLLM's own standard env-var discovery for that provider (e.g.
    OPENAI_API_KEY) instead — this project doesn't yet have a per-user,
    per-provider credential story; that's follow-up work, not something this
    function tries to anticipate.
    """
    return os.environ.get("STORY_SIM_ANTHROPIC_API_KEY") or None
