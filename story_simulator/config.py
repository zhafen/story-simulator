import os
from pathlib import Path

PROD_AGENT_ID = "agent_01AxMwvbKDkfbVZd73DLNiAy"
TEST_AGENT_ID = "agent_01FVJeTDVA2mMkYHzkaYvZLo"
ENVIRONMENT_ID = "env_01Rhk13fhp1wwS3RgiDQcK2g"

# The story-simulator's own component/field schema (position, character, ...).
# Every base_etl call needs this in `input_dirs` for its component types to
# be schema-validated — without it, validate_components has no field
# definitions for them and passes their data through unvalidated/untyped.
MANIFEST_DIR = Path(__file__).parent.parent / "manifest"

# The tracked, ever-growing "living world" save data (see cli.py's `--living`
# flag). Its setting.yaml carries the door mechanic that teleports the player
# forward in time and further from the origin each time they walk through it
# (see data/living_world/setting.yaml), and its save_dir accumulates history
# turn over turn as it's played. Not used to seed fresh sandboxes (see
# DEFAULT_WORLD_DIR for that) — `--living` points `save_dir` at this
# directory directly, so play there both reads and writes the tracked world.
LIVING_WORLD_DIR = Path(__file__).parent.parent / "data" / "living_world"

# A plain, hand-authored starting scenario (the player, a door, an empty
# expanse) with none of the living world's teleport/history mechanic. This is
# what a brand-new save_dir is seeded from by default (see
# story_simulator.world._seed_save_dir), so an ordinary throwaway sandbox
# starts from the same simple premise every time rather than wherever the
# living world currently stands.
DEFAULT_WORLD_DIR = Path(__file__).parent.parent / "data" / "default"
DEFAULT_SETTING_PATH = DEFAULT_WORLD_DIR / "setting.yaml"


def resolve_anthropic_api_key() -> str | None:
    """Read the Anthropic API key from its app-specific env var.

    Some hosting environments reserve ANTHROPIC_API_KEY for their own
    credential plumbing and strip user-supplied values under that name, so
    the key is read from STORY_SIM_ANTHROPIC_API_KEY here and passed
    explicitly to `anthropic.Anthropic(api_key=...)`. Returning None falls
    back to the SDK's own ANTHROPIC_API_KEY auto-discovery, which still
    works for local development.
    """
    return os.environ.get("STORY_SIM_ANTHROPIC_API_KEY") or None
