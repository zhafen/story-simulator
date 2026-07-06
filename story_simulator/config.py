import os

PROD_AGENT_ID = "agent_01AxMwvbKDkfbVZd73DLNiAy"
TEST_AGENT_ID = "agent_01FVJeTDVA2mMkYHzkaYvZLo"
ENVIRONMENT_ID = "env_01Rhk13fhp1wwS3RgiDQcK2g"


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
