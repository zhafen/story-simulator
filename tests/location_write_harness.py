"""Diagnostic harness for #73: compares different approaches to recording a
car's `location` once parked, measuring failure RATE across many reps per
approach rather than a single pass/fail. Deliberately NOT a pytest test (no
@pytest.mark.live here, not collected by the normal suite) -- this is a
comparison tool, not a regression gate. Run directly:

    uv run python tests/location_write_harness.py --approach baseline --reps 10

Isolates just the write-formatting step itself (see tests/data/scenarios/
location_write_isolated/scenario.yaml: one car, one already-resolvable
parking event, one spot) -- separate from arrival-order reasoning
(tests/test_race_placement_live.py) or driving/parking separation
(tests/test_parking_split_live.py), which are already covered elsewhere.

Currently one approach is implemented: "baseline" (today's direct-write
update_registry mechanism, the only approach that exists right now). More
approaches -- variations on it, and #74's guided multi-round-trip
formatting once that's built -- get added to _APPROACHES as they're
designed; the run/measurement machinery below doesn't change per-approach.
"""

import argparse
import tempfile
from pathlib import Path

from test_human_validated import HeadlessSession, _load_registrar, _location, _parked_at

REPO_ROOT = Path(__file__).parent.parent
SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "location_write_isolated"

# Today's only approach: the model composes and writes correctly-formatted
# entity-first YAML directly via update_registry, same mechanism
# test_race_placement_live.py / test_parking_split_live.py exercise.
_BASELINE_INSTRUCTION = (
    "Call advance_simulation and answer its prompts (resolve, then plan) until its "
    "status is \"done\" -- there is only one event. Record via update_registry that "
    "car_a parked in parking_spot_1, plus car_a_park's own outcome and event_state. "
    "Don't narrate anything back to me."
)

_APPROACHES = {
    "baseline": _BASELINE_INSTRUCTION,
}


def run_one(approach: str, tmp_dir: Path) -> tuple[bool, str]:
    """One rep: opens a fresh world, asks the model to record car_a's
    location under the given approach, returns (success, narration) --
    narration kept for diagnosing failures after the fact, not just the
    pass/fail count."""
    save_dir = tmp_dir / "save"
    instruction = _APPROACHES[approach]
    with HeadlessSession(save_dir) as session:
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {instruction}"
        )
        r = _load_registrar(save_dir, narration)
        success = _parked_at(_location(r, "car_a"), "parking_spot_1")
        return success, narration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approach", choices=sorted(_APPROACHES), default="baseline")
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()

    successes = 0
    failures: list[str] = []
    for i in range(args.reps):
        with tempfile.TemporaryDirectory() as tmp:
            ok, narration = run_one(args.approach, Path(tmp))
            successes += ok
            print(f"[{args.approach}] rep {i + 1}/{args.reps}: {'PASS' if ok else 'FAIL'}")
            if not ok:
                failures.append(narration)

    rate = successes / args.reps
    print(f"\n[{args.approach}] {successes}/{args.reps} = {rate:.0%}")
    if failures:
        print("\nFailure narrations:")
        for n in failures:
            print(f"  - {n!r}")


if __name__ == "__main__":
    main()
