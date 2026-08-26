"""Shared pytest fixtures for tests/test_human_validated/ -- promotes
helpers.py's existing per-test-call machinery (the responder env var,
_load_registrar) into real fixtures, plus a new turn_stepper for
turn-by-turn (stepwise) execution. See docs/manifest/story-simulator.yaml's
human_validated_test_framework.dependencies subtree for why each of
these exists.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest

from emc2p.registrar import Registrar

from test_human_validated.helpers import (
    DEFAULT_LIVE_TEST_RESPONDER,
    LIVE_TEST_RESPONDER_ENV_VAR,
    _load_registrar,
)


@pytest.fixture
def responder(request: pytest.FixtureRequest) -> str:
    """The responder choice (host/subagent/keyed_subagent) for this test.

    Resolves the same way session construction's own fallback already
    does (an explicit value wins, else the env var, else the hard-coded
    default) -- parametrize per-test with
    `@pytest.mark.parametrize("responder", ["host"], indirect=True)`
    rather than only being able to flip the whole suite's default via
    STORY_SIM_LIVE_TEST_RESPONDER.
    """
    explicit = getattr(request, "param", None)
    if explicit is not None:
        return explicit
    return os.environ.get(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)


@pytest.fixture
def scenario_registrar() -> Callable[[Path, str], Registrar]:
    """Loads a scenario's registrar after confirming its save_dir's schema
    actually exists -- a fixture wrapping helpers._load_registrar, so
    every scenario's tests.py can request `scenario_registrar` instead of
    importing the private helper directly.

    Returns a callable rather than a Registrar directly: which save_dir a
    given test needs is only known inside the test itself (after driving
    a session to completion), not at fixture-setup time.
    """
    return _load_registrar


@pytest.fixture
def turn_stepper() -> Callable[..., None]:
    """Drives a session one turn at a time, optionally running a check
    after each step -- for scenarios that need to assert on intermediate
    state, not just the final result, complementing today's
    run-to-completion tests (one open-ended send_turn call).

    Usage: `turn_stepper(session, ["do X", "do Y"], check=lambda: ...)`.
    """
    def _step(session, turns: list[str], check: Callable[[], None] | None = None) -> None:
        for turn in turns:
            session.send_turn(turn)
            if check is not None:
                check()
    return _step
