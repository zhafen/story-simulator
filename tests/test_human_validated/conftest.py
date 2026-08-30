"""Shared pytest fixtures for tests/test_human_validated/: responder and turn_stepper.

See docs/manifest/story-simulator.yaml's human_validated_test_framework
subtree for why each fixture exists.
"""

from __future__ import annotations

from typing import Callable

import pytest

from emc2p.testing.responder_fixture import make_responder_fixture

from test_human_validated.helpers import (
    DEFAULT_LIVE_TEST_RESPONDER,
    LIVE_TEST_RESPONDER_ENV_VAR,
)

# The param > env var > default resolution is generic; only the env var
# name/default are story-simulator-specific.
responder = make_responder_fixture(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)


@pytest.fixture
def turn_stepper() -> Callable[..., None]:
    """Drives a session one turn at a time, optionally checking state after each step.

    Usage: `turn_stepper(session, ["do X", "do Y"], check=lambda: ...)`.
    """
    def _step(session, turns: list[str], check: Callable[[], None] | None = None) -> None:
        for turn in turns:
            session.send_turn(turn)
            if check is not None:
                check()
    return _step
