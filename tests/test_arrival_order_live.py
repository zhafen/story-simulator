"""Isolated, disposable live regression: does a weak model reason about
event *arrival order* correctly when nothing else rides on the answer --
separate from tests/test_human_validated.py::test_car_parking_core_sim,
which conflates arrival-order reasoning with picking the right component
to record a resulting parking spot.

Investigating task #57 (the recurring bug where a weak model assumes a
different, not-yet-resolved car's trip has already finished, e.g. "car_a
already took the spot" when car_a_trip -- end_time 1800 -- hasn't resolved
at all yet). Hypothesis: some of the confusion comes from rolling
"driving" and "parking" into one event, not from the arrival-order
reasoning itself. tests/data/scenarios/arrival_order/scenario.yaml reuses
the exact same start_time/duration facts as the parking scenario (so the
correct order is identical: car_b end_time 1020, car_c 1080, car_a 1800)
but drops the restaurant/parking-spot framing entirely -- there is nothing
to reason about *except* arrival order.

Quick and deliberately disposable: delete this file and
tests/data/scenarios/arrival_order/ to remove it; nothing else references
either.
"""

from pathlib import Path

import pytest

from test_human_validated import HeadlessSession, _load_registrar
from iacs.registrar import Registrar
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent
ARRIVAL_ORDER_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "arrival_order"

_RESOLVE_ARRIVAL_ORDER_INSTRUCTION = (
    "Call advance_simulation. Answer its first prompt (resolving the next event whose "
    "end_time has been reached) by recording, via update_registry, that event's own "
    "outcome and event_state (complete). The outcome text must state plainly whether "
    "any OTHER car's own trip has already finished by this point in time -- if none "
    "have, say so explicitly rather than guessing or assuming. Don't answer the second "
    "(plan) prompt, and don't call advance_simulation a second time -- stop right after "
    "that one update_registry write."
)


def _outcome_text(registrar: Registrar, alias: str) -> str | None:
    df = safe_view_current(registrar, "outcome.value", aliases=alias)
    if df is None or df.empty:
        return None
    return str(df.iloc[-1]["outcome.value"])


def _wrongly_claims_already_arrived(outcome: str, other_car: str) -> bool:
    """Heuristic, not exact-phrasing -- free text can say this many ways.
    Only meant to catch the specific bug this test is checking for (a
    car whose own trip hasn't resolved yet being narrated as if it had),
    not to validate correct phrasing positively."""
    text = outcome.lower()
    if other_car not in text:
        return False
    wrong_signals = ["already", "arrived", "took", "ahead", "before", "earlier", "first"]
    return any(signal in text for signal in wrong_signals)


@pytest.mark.live
def test_arrival_order_reasoning_in_isolation(tmp_path):
    """car_b_trip is the first-popped event (soonest end_time, 1020) --
    nothing else has resolved yet, so the outcome recorded for it must not
    claim car_a (end_time 1800, last to actually finish) already arrived."""
    save_dir = tmp_path / "test_save"

    with HeadlessSession(save_dir) as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={ARRIVAL_ORDER_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RESOLVE_ARRIVAL_ORDER_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)
        outcome = _outcome_text(r, "car_b_trip")
        print(f"car_b_trip outcome: {outcome!r}")
        assert outcome is not None, f"No outcome recorded for car_b_trip -- narration: {narration!r}"
        assert not _wrongly_claims_already_arrived(outcome, "car_a"), (
            "car_b_trip's outcome wrongly implies car_a's trip (end_time 1800, actually "
            f"last to finish) had already resolved -- outcome: {outcome!r}, narration: {narration!r}"
        )
        assert not _wrongly_claims_already_arrived(outcome, "car_c"), (
            "car_b_trip's outcome wrongly implies car_c's trip (end_time 1080, not yet "
            f"resolved either) had already resolved -- outcome: {outcome!r}, narration: {narration!r}"
        )
