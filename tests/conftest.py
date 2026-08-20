"""Shared fixtures/helpers for story-simulator's own top-level test suite."""

from unittest.mock import MagicMock


def _make_ctx():
    """Return a minimal mock Context whose session supports weak references."""
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx
