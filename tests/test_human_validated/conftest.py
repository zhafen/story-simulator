"""Shared pytest fixtures for tests/test_human_validated/: responder and turn_stepper.

See docs/manifest/story-simulator.yaml's human_validated_test_framework
subtree for why each fixture exists.
"""

from __future__ import annotations

from typing import Callable

import pytest

from emc2p.testing.live_trial import make_live_trial_fixture, pytest_runtest_makereport  # noqa: F401
from emc2p.testing.responder_fixture import make_responder_fixture

from test_human_validated.helpers import (
    DEFAULT_LIVE_TEST_RESPONDER,
    LIVE_TEST_RESPONDER_ENV_VAR,
    LIVE_TRIAL_ENV_VAR,
    LIVE_TRIAL_RESULTS_DIR,
    REPO_ROOT,
)

# The param > env var > default resolution is generic; only the env var
# name/default are story-simulator-specific.
responder = make_responder_fixture(LIVE_TEST_RESPONDER_ENV_VAR, DEFAULT_LIVE_TEST_RESPONDER)

# live_trial reruns STORY_SIM_LIVE_TRIALS times (default 1), recording
# each run's pass/fail to .live_trial_results/<test name>.csv.
live_trial, pytest_generate_tests = make_live_trial_fixture(
    results_dir=LIVE_TRIAL_RESULTS_DIR, repo_root=REPO_ROOT, env_var=LIVE_TRIAL_ENV_VAR
)


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
