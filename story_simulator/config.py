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

# The world's starting premise (the player, the door, the empty expanse) as a
# hand-authored EC save file. Seeded into any brand-new save_dir (see
# story_simulator.world._seed_default_setting) so a fresh game always starts
# from this premise instead of one the Resolver has to invent unprompted.
DEFAULT_SETTING_PATH = Path(__file__).parent.parent / "data" / "default" / "setting.yaml"


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
