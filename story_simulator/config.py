"""Shared configuration: file paths, source identifiers, and credential lookup.

Every other story_simulator module imports from here rather than
hardcoding these paths/constants itself, so there's one place that knows
where the manifest, save-data seeds, and world-registry source key live.
"""

import hashlib
import os
import urllib.parse
from pathlib import Path

# The one source key every direct registrar.update() call across this project
# (mcp_server.py, spatial.py) must merge under — iacs hashes an entity's ID
# from (source key, entity path), so a different key at any call site would
# fork a duplicate entity instead of updating the original. See
# docs/manifest/story-simulator.yaml: story_simulator_mission.single_shared_source_key.
WORLD_FILE_ID = "world"

# The story-simulator's own component/field schema (position, character, ...).
# Every base_etl call needs this in `input_dirs` for its component types to
# be schema-validated — without it, validate_components has no field
# definitions for them and passes their data through unvalidated/untyped.
MANIFEST_DIR = Path(__file__).parent.parent / "manifest"

# The tracked, ever-growing "living world" save data — a `scenario_dir` a
# caller can pass to `start_world` instead of the plain default. Its
# scenario.yaml carries a door mechanic that teleports the player forward in
# time and further from the origin each time they walk through it (see
# data/living_world/scenario.yaml), and its own directory accumulates history
# turn over turn as it's played, unlike a fresh save_dir seeded from
# DEFAULT_WORLD_DIR.
LIVING_WORLD_DIR = Path(__file__).parent.parent / "data" / "living_world"

# A plain, hand-authored starting scenario (the player, a door, an empty
# expanse) with none of the living world's teleport/history mechanic. This is
# what `start_world` seeds a save_dir from when no `scenario_dir` is given,
# so an ordinary throwaway save always starts from the same simple premise
# rather than wherever the living world currently stands.
DEFAULT_WORLD_DIR = Path(__file__).parent.parent / "data" / "default"


# Registry backend: any ibis.connect-resolvable URL works (Registry is
# backend-agnostic); Postgres is the default and verified one. Matches GitHub
# Actions' `postgres:` service container, so CI needs no override; local dev
# needs a matching database server (or STORY_SIM_DATABASE_DSN pointed
# elsewhere). See registry_url's docstring for why Postgres specifically.
DEFAULT_DATABASE_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


def resolve_database_dsn() -> str:
    """Read the registry database's connection string, minus any save's own schema."""
    return os.environ.get("STORY_SIM_DATABASE_DSN") or DEFAULT_DATABASE_DSN


def registry_schema_name(save_dir: Path) -> str:
    """Derive a stable schema name for `save_dir`'s registry data.

    "Schema" here means a database namespace (`CREATE SCHEMA foo`, a
    directory-like grouping of tables within one database) -- not a single
    table's column structure. Every save's registry has the same table
    names (`position`, `character`, ...), so without each save living in
    its own schema, two saves sharing one database would collide on those
    table names directly.

    A hash of the resolved absolute path, not the path itself: a SQL
    identifier is typically case-folded and can't contain characters a
    filesystem path routinely does (dashes, dots, mixed case that would
    silently collide once lowercased), so a hash sidesteps sanitizing
    arbitrary path text while still mapping the same save_dir to the same
    schema every time `start_world` reopens it.
    """
    digest = hashlib.sha256(str(Path(save_dir).resolve()).encode()).hexdigest()
    return f"save_{digest[:24]}"


def registry_url(save_dir: Path) -> str:
    """Return the `ibis.connect`-able URL for `save_dir`'s registry schema.

    Points at the same database every save shares (`resolve_database_dsn`),
    scoped to that save's own schema via the `schema` query param. The
    schema itself is not created by connecting to it -- with the current
    Postgres backend, an unknown schema in the connection's search_path is
    silently skipped rather than erroring, which would mean every
    not-yet-created save quietly falls through to whatever's next on the
    path (typically `public`) instead of failing loudly. Callers must
    create it first (see mcp_server._ensure_postgres_schema); a different
    backend may need a different equivalent.

    Postgres specifically (not the DuckDB this registry used before) because
    a live MCP session needs its connection to stay open for the session's
    whole lifetime while other processes still read/write concurrently --
    DuckDB's file-based storage locks out every other connection for as long
    as one process holds it open, which any client/server backend avoids.
    """
    __iacs__ = {"solution of": "story_simulator_mission.concurrent_readable_registry"}
    dsn = resolve_database_dsn()
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

    Only covers Anthropic-flavored `model:` strings. An agent configured for
    another provider relies on LiteLLM's own standard env-var discovery for
    that provider instead (e.g. OPENAI_API_KEY) — see
    docs/manifest/story-simulator.yaml: story_simulator_mission.per_provider_credentials.
    """
    return os.environ.get("STORY_SIM_ANTHROPIC_API_KEY") or None


# Every module layered on top of story_simulator.core's base event loop --
# see core.py's own docstring for what "base" guarantees regardless of
# which of these are active. "character" is the only one advance_simulation
# itself branches on today (whether a due entity gets resolved by a real
# human/host via character_communication+resolve_event, or generically via
# resolve_base_event); the rest (npc, physics, terrain, spatial) don't
# change the loop's own control flow yet -- they're already reachable as
# separately-callable tools (advance_npc_turn, resolve_physics,
# generate_terrain, perceive) regardless of this set, and are only tracked
# here so a deployment can describe/discover which are meant to be in play.
ALL_MODULES = frozenset({"character", "npc", "physics", "terrain", "spatial"})


def enabled_modules() -> frozenset[str]:
    """Which optional modules are active for this deployment.

    Read from STORY_SIM_MODULES, a comma-separated subset of ALL_MODULES
    (e.g. "character,spatial"). Unset means every module -- the
    fully-featured behavior this project shipped before any of them were
    optional -- for backward compatibility; an explicitly empty value
    ("STORY_SIM_MODULES=") means none: the base event-driven simulation
    with nothing layered on top at all.
    """
    raw = os.environ.get("STORY_SIM_MODULES")
    if raw is None:
        return ALL_MODULES
    return frozenset(m.strip() for m in raw.split(",") if m.strip())
