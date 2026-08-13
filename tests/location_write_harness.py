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

Two approaches are compared: "baseline" (today's direct single-shot
update_registry write) and "confirm" (#74's opt-in preview=True /
confirm_token round trip -- write, review what it's about to commit
against what's already there, then confirm or correct). Both share the
same run/measurement machinery below; only the instruction text differs.
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

# #74's preview/confirm alternative: write with preview=True first, check
# the returned review (referenced/available component types, stats+peek
# for each referenced type) against what was intended, then either confirm
# with the returned confirm_token or correct and re-preview.
_CONFIRM_INSTRUCTION = (
    "Call advance_simulation and answer its prompts (resolve, then plan) until its "
    "status is \"done\" -- there is only one event. Record via update_registry that "
    "car_a parked in parking_spot_1, plus car_a_park's own outcome and event_state -- "
    "but first call update_registry with preview=True (and your yaml_string) to review "
    "what it would write before committing. Check the review's list of components your "
    "write references and the stats+peek for each against what you actually intend to "
    "record; if anything looks wrong, correct your yaml_string and preview again instead "
    "of confirming. Once it looks right, call update_registry again with the exact "
    "confirm_token it gave you (and no yaml_string) to actually merge it. "
    "Don't narrate anything back to me."
)

_APPROACHES = {
    "baseline": _BASELINE_INSTRUCTION,
    "confirm": _CONFIRM_INSTRUCTION,
}


def run_one(approach: str, tmp_dir: Path) -> tuple[bool, str, dict]:
    """One rep: opens a fresh world, asks the model to record car_a's
    location under the given approach, returns (success, narration,
    usage) -- narration kept for diagnosing failures after the fact, not
    just the pass/fail count; usage (see HeadlessSession.usage_summary)
    kept so #75's cost comparison isn't limited to whichever approach
    happens to get run last."""
    save_dir = tmp_dir / "save"
    instruction = _APPROACHES[approach]
    with HeadlessSession(save_dir) as session:
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {instruction}"
        )
        r = _load_registrar(save_dir, narration)
        success = _parked_at(_location(r, "car_a"), "parking_spot_1")
        return success, narration, session.usage_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approach", choices=sorted(_APPROACHES), default="baseline")
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()

    successes = 0
    failures: list[str] = []
    total_cost_usd = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    for i in range(args.reps):
        with tempfile.TemporaryDirectory() as tmp:
            ok, narration, usage = run_one(args.approach, Path(tmp))
            successes += ok
            total_cost_usd += usage["total_cost_usd"]
            total_input_tokens += usage["input_tokens"]
            total_output_tokens += usage["output_tokens"]
            print(
                f"[{args.approach}] rep {i + 1}/{args.reps}: {'PASS' if ok else 'FAIL'} "
                f"(${usage['total_cost_usd']:.4f})"
            )
            if not ok:
                failures.append(narration)

    rate = successes / args.reps
    print(f"\n[{args.approach}] {successes}/{args.reps} = {rate:.0%}")
    print(
        f"[{args.approach}] total: ${total_cost_usd:.4f}, "
        f"{total_input_tokens} input tokens, {total_output_tokens} output tokens "
        f"(${total_cost_usd / args.reps:.4f}/rep)"
    )
    if failures:
        print("\nFailure narrations:")
        for n in failures:
            print(f"  - {n!r}")


if __name__ == "__main__":
    main()
