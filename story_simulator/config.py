"""Shared configuration: file paths, source identifiers, and credential lookup.

Every other story_simulator module imports from here rather than
hardcoding these paths/constants itself, so there's one place that knows
where the manifest, save-data seeds, and world-registry source key live.
"""

import hashlib
import os
import urllib.parse
from pathlib import Path

# iacs hashes an entity's ID from (source key, entity path) — merging two
# YAML strings under the SAME source key with the SAME entity path (e.g.
# "player") resolves to the SAME entity, letting a later write attach to
# data an earlier write created; merging under a DIFFERENT source key would
# hash to a different entity_id even for the identical path, silently
# forking a duplicate instead of updating the original. Every direct
# registrar.update() call across this project (story_simulator.mcp_server,
# story_simulator.spatial) must therefore use this one shared key — that's
# what makes `same_as`-based updates from different tool calls (perceive's
# active-tag sync, update_registry, ...) reliably land on the same
# persistent entities rather than fragmenting into duplicates. Not a
# meaningful name in its own right (any consistent string would do) — it
# exists purely so every write site agrees on it.
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


# DuckDB's file-based storage locks out every other connection -- reader or
# writer, same or different process -- for as long as one process holds it
# open, which is fundamentally incompatible with a live MCP session (the
# registry needs to stay open for the session's whole lifetime) ever being
# inspected from anywhere else. Postgres is a real server: any number of
# processes can hold their own connection to the same schema concurrently,
# each seeing current committed state, with no coordination between them
# needed. Defaults match the credentials GitHub Actions' `postgres:` service
# container ships with, so CI needs no override; local dev needs a Postgres
# server matching this (or STORY_SIM_POSTGRES_DSN set to point elsewhere).
DEFAULT_POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


def resolve_postgres_dsn() -> str:
    """Read the registry database's connection string, minus any save's own schema."""
    return os.environ.get("STORY_SIM_POSTGRES_DSN") or DEFAULT_POSTGRES_DSN


def registry_schema_name(save_dir: Path) -> str:
    """Derive a stable Postgres schema name for `save_dir`'s registry data.

    A hash of the resolved absolute path, not the path itself: Postgres
    identifiers are case-folded and can't contain characters a filesystem
    path routinely does (dashes, dots, mixed case that would silently
    collide once lowercased), so a hash sidesteps sanitizing arbitrary path
    text while still mapping the same save_dir to the same schema every
    time `start_world` reopens it.
    """
    digest = hashlib.sha256(str(Path(save_dir).resolve()).encode()).hexdigest()
    return f"save_{digest[:24]}"


def registry_url(save_dir: Path) -> str:
    """Return the `ibis.connect`-able URL for `save_dir`'s registry schema.

    Points at the same database every save shares (`resolve_postgres_dsn`),
    scoped to that save's own schema via the `schema` query param `ibis`'s
    postgres backend reads off the URL. The schema itself is not created by
    connecting to it -- an unknown schema in Postgres's search_path is
    silently skipped rather than erroring, which would mean every
    not-yet-created save quietly falls through to whatever's next on the
    path (typically `public`) instead of failing loudly. Callers must
    `CREATE SCHEMA IF NOT EXISTS` it first (see mcp_server._ensure_schema).
    """
    dsn = resolve_postgres_dsn()
    schema = registry_schema_name(save_dir)
    separator = "&" if urllib.parse.urlparse(dsn).query else "?"
    return f"{dsn}{separator}schema={schema}"


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
