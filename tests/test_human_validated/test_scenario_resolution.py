"""Live regressions: does the connected model ("host" responder) reason
correctly about two different scenarios built on the same underlying
first-come-first-served facts (car_b arrives/finishes first, car_c
second, car_a last)?

- **race** (task #57): a bare arrival-order check with nothing else to
  reason about -- three cars, one race, each car's own `race_placement`
  recorded directly. Permanent regression, checked exactly via that
  dedicated component rather than by matching substrings in freeform
  outcome text (a heuristic text match produced a false positive during
  the original diagnostic -- see docs/manifest/history.yaml).
- **parking_split** (task #65, investigating #57): the same arrival-order
  reasoning, but with a real consequence attached (which parking spot each
  car gets) and each car's drive/park decision split into two separate,
  pre-planned events rather than one combined trip. Isolates whether
  splitting the events keeps the same correctness a combined event lost --
  see tests/data/scenarios/parking_split/scenario.yaml.

Consolidated into one parametrized test rather than two near-identical
modules: both scenarios are the same shape from the harness's own point of
view -- a scenario_dir is the input (a manifest, same as emc2p/iacs's own
examples), one open-ended live-session turn is the transformation, and the
loaded registrar's final state is compared against a hand-written
tests/test_human_validated/expected/<name>.py fixture via
`emc2p.testing.expected_fixtures.assert_subset` -- the same
load/transform/compare-to-expected.py framework iacs's own
test_human_validated.py builds on (see that module's own docstring),
just with a live session standing in for the in-process Hamilton driver
iacs/emc2p use it for. What actually differs between the two scenarios
(the turn instruction, and which fields need checking -- location's
substring-tolerant match vs race_placement's exact one) stays
scenario-specific via each `Case`'s own `checks` callable; what doesn't
differ (event_state, write-order timing evidence) is checked once, generically.

Deliberately checks only *final* state, not turn-by-turn state (see
#61/docs/manifest/history.yaml: project_history.
live_tests_decoupled_from_turn_count) -- each case runs its whole scenario
in one open-ended instruction, in as many or as few advance_simulation
round-trips as the model wants. Order evidence instead comes from each
expected write's own recorded world time (`helpers._assert_write_order`),
confirming it was recorded while its own event resolved, not retroactively.

test_race_placement_via_keyed_subagent.py stays separate: same "race"
scenario and expected fixture, but a deliberately different axis (which
responder answers each event's judgment call, not which scenario runs) --
not a case of this same harness.
"""

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

from emc2p.testing.expected_fixtures import assert_subset
from test_human_validated.helpers import (
    McpClientSession,
    _assert_write_order,
    _event_states,
    _load_registrar,
    _parked_at,
    _placement,
    load_expected,
)

REPO_ROOT = Path(__file__).parent.parent.parent
SCENARIOS_DIR = REPO_ROOT / "tests" / "data" / "scenarios"

# Deliberately one open-ended instruction per case, not one per event (see
# #61/docs/manifest/history.yaml) -- checks the final result and order, not turn count.
_RUN_TO_DONE_RACE_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names) until its status is \"done\". For each event's resolve step, "
    "record via update_registry that event's own outcome and event_state (complete), AND "
    "that car's own race_placement -- its 1-indexed finishing position among all three cars "
    "(1 = first to finish), based on which cars' own trips have already finished by this "
    "point in time. Don't narrate anything back to me."
)

_RUN_TO_DONE_SPLIT_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names, recording each decision via update_registry) until its "
    "status is \"done\". There are two events per car: a driving event (record its own "
    "outcome and event_state as complete once the car has arrived -- don't decide where "
    "it parks yet, that's the separate parking event's own job) and a parking event (look "
    "up what's already taken, then record via update_registry that car's own location, "
    "plus that event's own outcome and event_state). Don't narrate anything back to me."
)


def _check_race(r, expected: ModuleType) -> None:
    """race_placement is a plain int field the model fills directly -- an exact
    match (assert_subset) is the right check, no phrasing to be lenient about."""
    placements = {alias: _placement(r, alias) for alias in expected.race_placement}
    assert_subset("race_placement", expected.race_placement, placements)


def _check_parking_split(r, expected: ModuleType) -> None:
    """location is a freeform phrase (see helpers._parked_at) -- a live model's
    correct answer can reasonably come out phrased several ways, so this checks
    a substring rather than assert_subset's exact match."""
    for alias, spot in expected.location.items():
        assert _parked_at(r.get_current_value("location", alias=alias), spot), (
            f"{alias} should be parked at {spot}"
        )


@dataclass(frozen=True)
class Case:
    name: str
    scenario_dir: Path
    instruction: str
    checks: Callable[[object, ModuleType], None]
    # Matches McpClientSession's own defaults -- only parking_split (below)
    # needs to override these.
    turn_timeout: float = 240
    session_timeout: float = 120


CASES = [
    Case(
        name="race",
        scenario_dir=SCENARIOS_DIR / "race",
        instruction=_RUN_TO_DONE_RACE_INSTRUCTION,
        checks=_check_race,
    ),
    Case(
        name="parking_split",
        scenario_dir=SCENARIOS_DIR / "parking_split",
        instruction=_RUN_TO_DONE_SPLIT_INSTRUCTION,
        checks=_check_parking_split,
        # A "host"-responder run driving all six resolve+plan steps itself
        # (twice as many as the three-event race case) routinely needs more
        # than the default 120s session_timeout -- confirmed live it times
        # out mid-event otherwise, not on anything about the simulation itself.
        turn_timeout=420,
        session_timeout=420,
    ),
]


@pytest.mark.live
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_scenario_resolves_correctly(case: Case, tmp_path: Path):
    """Run one case's scenario to completion under a live "host"-responder
    session, then check its final registry state against its own known-
    correct expected.py fixture (case-specific fields via `case.checks`,
    event_state/write-order timing generically -- see this module's own
    docstring)."""
    save_dir = tmp_path / "test_save"

    # Every case's whole point is the *connected* model's own reasoning --
    # explicit override of McpClientSession's keyed_subagent default.
    with McpClientSession(
        save_dir, responder="host", turn_timeout=case.turn_timeout, session_timeout=case.session_timeout
    ) as session:
        print(f"McpClientSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={case.scenario_dir} "
            f"to open a story-simulator world. Then {case.instruction}"
        )
        r = _load_registrar(save_dir, narration)
        expected = load_expected(case.name)

        try:
            case.checks(r, expected)
            assert_subset("event_state", expected.event_state, _event_states(r))
            _assert_write_order(r, expected)
        except AssertionError as exc:
            raise AssertionError(f"{exc} -- narration: {narration!r}") from exc
