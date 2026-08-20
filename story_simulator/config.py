"""Shared configuration: file paths, source identifiers, and credential lookup.

Every other story_simulator module imports from here rather than
hardcoding these paths/constants itself.
"""

import hashlib
import os
import urllib.parse
from pathlib import Path

# The story-simulator's own component/field schema (position, character,
# ...). Every base_etl call needs this in `input_dirs`, or types go unvalidated.
MANIFEST_DIR = Path(__file__).parent.parent / "manifest"

# The tracked, ever-growing "living world" save data -- a `scenario_dir`
# a caller can pass to `start_world` instead of the plain default.
LIVING_WORLD_DIR = Path(__file__).parent.parent / "data" / "living_world"

# A plain, hand-authored starting scenario (the player, a door, an empty
# expanse), with none of the living world's teleport/history mechanic.
DEFAULT_WORLD_DIR = Path(__file__).parent.parent / "data" / "default"


# Registry backend: any ibis.connect-resolvable URL works; Postgres is the
# default and verified one, matching GitHub Actions' `postgres:` service container.
DEFAULT_DATABASE_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


def resolve_database_dsn() -> str:
    """Read the registry database's connection string, minus any save's own schema."""
    return os.environ.get("STORY_SIM_DATABASE_DSN") or DEFAULT_DATABASE_DSN


def registry_schema_name(save_dir: Path) -> str:
    """Derive a stable schema name for `save_dir`'s registry data.

    "Schema" here means a database namespace, not a table's column
    structure -- every save's registry has the same table names, so each
    save needs its own schema to avoid colliding with another save's.

    A hash of the resolved absolute path, not the path itself: a SQL
    identifier can't safely hold arbitrary path characters (dashes, dots,
    case), so hashing sidesteps sanitizing while still mapping the same
    save_dir to the same schema on every reopen.
    """
    digest = hashlib.sha256(str(Path(save_dir).resolve()).encode()).hexdigest()
    return f"save_{digest[:24]}"


def registry_url(save_dir: Path) -> str:
    """Return the `ibis.connect`-able URL for `save_dir`'s registry schema.

    Scoped to that save's own schema via the `schema` query param.
    Connecting doesn't create the schema -- an unknown schema is silently
    skipped rather than erroring, so callers must create it first (see
    core._ensure_postgres_schema).

    Postgres specifically: a live MCP session needs its connection to stay
    open for the whole session while other processes read/write
    concurrently -- see docs/manifest/history.yaml:
    project_history.database_migrated_to_postgres.
    """
    __iacs__ = {"solution of": "story_simulator_mission.concurrent_readable_registry"}
    dsn = resolve_database_dsn()
    schema = registry_schema_name(save_dir)
    separator = "&" if urllib.parse.urlparse(dsn).query else "?"
    return f"{dsn}{separator}schema={schema}"


def resolve_anthropic_api_key() -> str | None:
    """Read the Anthropic API key from its app-specific env var.

    Some hosting environments reserve ANTHROPIC_API_KEY for their own
    credential plumbing and strip user-supplied values, so the key is read
    from STORY_SIM_ANTHROPIC_API_KEY instead. Returning None falls back to
    each SDK/LiteLLM's own ANTHROPIC_API_KEY auto-discovery.

    Only covers Anthropic-flavored `model:` strings; other providers rely
    on LiteLLM's own env-var discovery instead (e.g. OPENAI_API_KEY).
    """
    return os.environ.get("STORY_SIM_ANTHROPIC_API_KEY") or None

# ALL_MODULES/enabled_modules() (the character/npc/physics/terrain/spatial
# optional-module toggle) removed along with the code it gated.

_EVENT_RESPONDERS = ("host", "subagent", "keyed_subagent")

# LiteLLM model string `keyed_subagent_model()` falls back to -- any
# provider LiteLLM supports; DeepSeek is the current pick (see docs/manifest/history.yaml).
DEFAULT_KEYED_SUBAGENT_MODEL = "deepseek/deepseek-chat"

# Wall-clock seconds `keyed_subagent_time_budget_seconds()` falls back to.
# Deliberately well under Claude Code's own ~60s per-MCP-tool-call timeout.
DEFAULT_KEYED_SUBAGENT_TIME_BUDGET_SECONDS = 30.0


def event_responder() -> str:
    """Which responder `core.resolve_event` should ask each time a base
    event's end_time is reached.

    "host" (default -- the connected agent decides inline, from its own
    accumulated context), "subagent" (ask it to delegate to its own
    isolated subagent mechanism instead, e.g. Claude Code's Agent/Task
    tool), or "keyed_subagent" (answered directly, in-process, via
    `keyed_subagent_model()` and story-simulator's own API key, with its
    own registry tool access dispatched in-process rather than over MCP
    -- though it still checks in with the host over MCP once its own
    time budget runs out) -- see `story_simulator.resolve`'s module
    docstring for what each buys and "subagent"'s one known gap.

    Read from STORY_SIM_RESPONDER rather than a `start_world`
    argument -- a deployment-wide choice about how its connected agent
    should be used, not something that varies save to save. Defaults to
    "host" (today's only behavior) so nothing changes for a deployment
    that hasn't opted in. An unrecognized value raises rather than
    silently falling back to "host", so a typo'd env var fails loud
    instead of quietly never delegating.
    """
    value = os.environ.get("STORY_SIM_RESPONDER", "host")
    if value not in _EVENT_RESPONDERS:
        raise ValueError(f"STORY_SIM_RESPONDER must be one of {_EVENT_RESPONDERS}, got {value!r}")
    return value


def keyed_subagent_model() -> str:
    """Which LiteLLM model string the "keyed_subagent" responder calls
    directly (see `story_simulator.resolve`/`story_simulator.keyed_subagent`).

    Read from STORY_SIM_SUBAGENT_MODEL so swapping models (DeepSeek, a
    Groq-hosted Llama, ...) is a config change, not a code change; the
    corresponding API key is resolved by LiteLLM itself from whichever
    env var that provider's LiteLLM integration expects (e.g.
    DEEPSEEK_API_KEY), not from anything in this module.
    """
    return os.environ.get("STORY_SIM_SUBAGENT_MODEL", DEFAULT_KEYED_SUBAGENT_MODEL)


def keyed_subagent_time_budget_seconds() -> float:
    """How many wall-clock seconds the "keyed_subagent" responder may
    keep answering judgment calls inline before checking in with the host.

    Checked within one `advance_simulation` call, instead of continuing
    unattended -- see `story_simulator.resolve.TurnReplay.resolve`. Read
    from STORY_SIM_SUBAGENT_TIME_BUDGET_SECONDS.
    """
    return float(
        os.environ.get(
            "STORY_SIM_SUBAGENT_TIME_BUDGET_SECONDS", DEFAULT_KEYED_SUBAGENT_TIME_BUDGET_SECONDS
        )
    )
