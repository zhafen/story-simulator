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

# The tracked, ever-growing "living world" save data — the game state
# everyone starts from by default (see cli.py's `--living` flag). Copied
# wholesale into any brand-new save_dir (see
# story_simulator.world._seed_from_living_world) so a fresh sandbox starts
# from wherever the living world currently stands rather than from scratch.
LIVING_WORLD_DIR = Path(__file__).parent.parent / "data" / "default"

# The world's starting premise (the player, the door, the empty expanse) as a
# hand-authored EC save file — the one part of the living world's save data
# that's always present, even before it's grown any further.
DEFAULT_SETTING_PATH = LIVING_WORLD_DIR / "setting.yaml"


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
