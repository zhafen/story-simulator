"""Live regression for this directory's own scenario.yaml: the same
arrival-order reasoning as the race scenario, but with a real
consequence attached (which parking spot each car gets) and each car's
drive/park decision split into two separate, pre-planned events rather
than one combined trip. Isolates whether splitting the events keeps the
same correctness a combined event lost.

A scenario_dir is the input (a manifest, same as emc2p/iacs's own
examples), one open-ended live-session turn is the transformation, and
the loaded registrar's final state is compared against this module's own
known-correct constants below via
`emc2p.testing.expected_fixtures.assert_subset` -- the same
load/transform/compare-to-expected framework iacs's own
test_human_validated.py builds on (see that module's own docstring),
just with a live session standing in for the in-process Hamilton driver
iacs/emc2p use it for.

The instruction sent below is deliberately generic ("run to done") --
any reasoning a responder needs to resolve a specific event correctly
(what to look up, what to record, and how) comes from the MCP server's
own resolve/plan prompts (see `core.resolve_event`/`plan_events`), not
from this test smuggling in scenario-specific hints no real deployment
would provide.

Deliberately checks only *final* state, not turn-by-turn state -- runs
the whole scenario in one open-ended instruction, in as many or as few
advance_simulation round-trips as the model wants. Order evidence
instead comes from each expected write's own recorded world time
(helpers._assert_write_order), confirming it was recorded while its own
event resolved, not retroactively.
"""

from pathlib import Path

import pytest

from emc2p.registrar import Registrar
from emc2p.testing.expected_fixtures import assert_subset
from story_simulator.config import registry_url
from test_human_validated.helpers import (
    create_session,
    _assert_write_order,
    _event_states,
)

SCENARIO_DIR = Path(__file__).parent


def _parked_at(location: str | None, spot: str) -> bool:
    """Loosely checks a recorded `location` value names `spot` (e.g.
    "parking_spot_1" or "street"), not any one exact phrasing.

    `location`'s own schema (manifest/builtins.yaml) calls it a "short
    freeform phrase" -- a model's correct answer can reasonably come out
    phrased several ways ("parked in
    parking_spot_1" vs. just "parking_spot_1") -- the model shouldn't
    have to guess the one exact wording a test hardcodes. Takes the
    value directly (e.g. from `registrar.get_current_value("location",
    alias=alias)`) rather than reading it itself.

    Scenario-specific, not shared -- tests/location_write_harness.py
    keeps its own copy rather than importing this one.
    """
    return location is not None and spot in location


# alias -> a substring that must appear in that car's recorded
# location.value (see _parked_at above) -- not an exact string, since a
# live model's own phrasing of "parked in parking_spot_1" reasonably varies.
EXPECTED_LOCATION = {
    "car_b": "parking_spot_1",
    "car_c": "parking_spot_2",
    "car_a": "street",
}

# alias -> expected event_state.value, once every drive/park event has resolved.
EXPECTED_EVENT_STATE = {
    "car_a_drive": "complete",
    "car_a_park": "complete",
    "car_b_drive": "complete",
    "car_b_park": "complete",
    "car_c_drive": "complete",
    "car_c_park": "complete",
}

# Order evidence: each car's location write should be time-stamped with its
# own *parking* event's end_time (not its driving event's), confirming the
# spot was assigned once that car's own parking event resolved.
EXPECTED_WRITE_ORDER = {
    "component_type": "location",
    "times": {"car_b": 1030, "car_c": 1090, "car_a": 1810},
}

_RUN_TO_DONE_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (recording each "
    "decision via update_registry) until its status is \"done\". Don't "
    "narrate anything back to me."
)


def _check_parking_split(r) -> None:
    """location is a freeform phrase (see _parked_at above) -- a live model's
    correct answer can reasonably come out phrased several ways, so this checks
    a substring rather than assert_subset's exact match."""
    for alias, spot in EXPECTED_LOCATION.items():
        assert _parked_at(r.get_current_value("location", alias=alias), spot), (
            f"{alias} should be parked at {spot}"
        )


@pytest.mark.live
def test_scenario_resolves_correctly(tmp_path: Path):
    """Run to completion under a live "host"-responder session, then check
    final registry state against this module's own EXPECTED_* constants
    (location by substring, event_state/write-order generically)."""
    save_dir = tmp_path / "test_save"

    # This test's whole point is the *connected* model's own reasoning --
    # explicit override of create_session's keyed_subagent default.
    #
    # A "host"-responder run driving all six resolve+plan steps itself
    # (twice as many as the race scenario's three events) routinely needs
    # more than create_session's own 120s/240s defaults, timing out
    # mid-event otherwise -- not on anything about the simulation itself.
    with create_session(save_dir, responder="host", turn_timeout=420, session_timeout=420) as session:
        print(f"agent session trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_INSTRUCTION}"
        )
        r = Registrar.load(registry_url(save_dir))

        try:
            _check_parking_split(r)
            assert_subset("event_state", EXPECTED_EVENT_STATE, _event_states(r))
            _assert_write_order(r, EXPECTED_WRITE_ORDER)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc
