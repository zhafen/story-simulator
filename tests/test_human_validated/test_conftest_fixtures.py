"""Fast (non-live) tests for tests/test_human_validated/conftest.py's own
fixtures -- responder, turn_stepper. No real session or database
involved; these only check the fixtures' own resolution/dispatch logic.
"""

from unittest.mock import MagicMock

import pytest

from test_human_validated.helpers import DEFAULT_LIVE_TEST_RESPONDER, LIVE_TEST_RESPONDER_ENV_VAR


class TestResponderFixture:
    def test_defaults_to_default_live_test_responder_with_no_env_var(self, responder, monkeypatch):
        monkeypatch.delenv(LIVE_TEST_RESPONDER_ENV_VAR, raising=False)
        assert responder == DEFAULT_LIVE_TEST_RESPONDER

    def test_reads_the_env_var_when_no_explicit_param(self, request, monkeypatch):
        # responder must be fetched *after* setenv, not requested as a
        # normal parameter -- ordinary fixture params are all resolved
        # before the test body runs, which would read the env var before
        # this test ever sets it.
        monkeypatch.setenv(LIVE_TEST_RESPONDER_ENV_VAR, "host")
        assert request.getfixturevalue("responder") == "host"

    @pytest.mark.parametrize("responder", ["subagent"], indirect=True)
    def test_explicit_param_wins_over_the_env_var(self, responder, monkeypatch):
        monkeypatch.setenv(LIVE_TEST_RESPONDER_ENV_VAR, "host")
        assert responder == "subagent"


class TestTurnStepperFixture:
    def test_sends_one_turn_at_a_time_in_order(self, turn_stepper):
        session = MagicMock()
        turn_stepper(session, ["first", "second", "third"])
        assert [c.args[0] for c in session.send_turn.call_args_list] == ["first", "second", "third"]

    def test_runs_check_after_every_turn(self, turn_stepper):
        session = MagicMock()
        check = MagicMock()
        turn_stepper(session, ["a", "b"], check=check)
        assert check.call_count == 2

    def test_no_check_is_optional(self, turn_stepper):
        session = MagicMock()
        turn_stepper(session, ["a"])  # must not raise with no check given
        session.send_turn.assert_called_once_with("a")
