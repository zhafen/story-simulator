"""Live regression for this directory's own scenario.yaml: the same
arrival-order reasoning as the race scenario, but with a real
consequence attached (which parking spot each car gets) and each car's
drive/park decision split into two separate, pre-planned events rather
than one combined trip. Isolates whether splitting the events keeps the
same correctness a combined event lost.

A scenario_dir is the input (a manifest, same as emc2p/iacs's own
examples), one open-ended live-session turn is the transformation, and
the loaded registrar's final state is compared against this directory's
own hand-written expected.py fixture via
`emc2p.testing.expected_fixtures.assert_subset` -- the same
load/transform/compare-to-expected.py framework iacs's own
test_human_validated.py builds on (see that module's own docstring),
just with a live session standing in for the in-process Hamilton driver
iacs/emc2p use it for.

Deliberately checks only *final* state, not turn-by-turn state -- runs
the whole scenario in one open-ended instruction, in as many or as few
advance_simulation round-trips as the model wants. Order evidence
instead comes from each expected write's own recorded world time
(helpers._assert_write_order), confirming it was recorded while its own
event resolved, not retroactively.
"""

from pathlib import Path

import pytest

from emc2p.testing.expected_fixtures import assert_subset, load_expected_module
from test_human_validated.helpers import (
    McpClientSession,
    _assert_write_order,
    _event_states,
    _load_registrar,
    _parked_at,
)

SCENARIO_DIR = Path(__file__).parent
EXPECTED = load_expected_module(SCENARIO_DIR / "expected.py")

_RUN_TO_DONE_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names, recording each decision via update_registry) until its "
    "status is \"done\". There are two events per car: a driving event (record its own "
    "outcome and event_state as complete once the car has arrived -- don't decide where "
    "it parks yet, that's the separate parking event's own job) and a parking event (look "
    "up what's already taken, then record via update_registry that car's own location, "
    "plus that event's own outcome and event_state). Don't narrate anything back to me."
)


def _check_parking_split(r) -> None:
    """location is a freeform phrase (see helpers._parked_at) -- a live model's
    correct answer can reasonably come out phrased several ways, so this checks
    a substring rather than assert_subset's exact match."""
    for alias, spot in EXPECTED.location.items():
        assert _parked_at(r.get_current_value("location", alias=alias), spot), (
            f"{alias} should be parked at {spot}"
        )


@pytest.mark.live
def test_scenario_resolves_correctly(tmp_path: Path):
    """Run to completion under a live "host"-responder session, then check
    final registry state against expected.py (location by substring,
    event_state/write-order generically)."""
    save_dir = tmp_path / "test_save"

    # This test's whole point is the *connected* model's own reasoning --
    # explicit override of McpClientSession's keyed_subagent default.
    #
    # A "host"-responder run driving all six resolve+plan steps itself
    # (twice as many as the race scenario's three events) routinely needs
    # more than McpClientSession's own 120s/240s defaults, timing out
    # mid-event otherwise -- not on anything about the simulation itself.
    with McpClientSession(save_dir, responder="host", turn_timeout=420, session_timeout=420) as session:
        print(f"McpClientSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        try:
            _check_parking_split(r)
            assert_subset("event_state", EXPECTED.event_state, _event_states(r))
            _assert_write_order(r, EXPECTED)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc
