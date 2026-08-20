"""Shared fixtures/helpers for story-simulator's own top-level test suite."""

from unittest.mock import MagicMock

from story_simulator import core


def _make_ctx():
    """Return a minimal mock Context whose session supports weak references."""
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


def update_registry(yaml_string: str, *, ctx) -> str:
    """Stand-in for the `update_registry` tool this server used to define
    itself -- now `core.registrar_sessions`' own method (mounted directly
    onto the real server; see `story_simulator.mcp_server`), so tests call
    it the same way a mounted tool's wrapper would."""
    return core.registrar_sessions.update_registry(ctx.request_context.session, yaml_string)
