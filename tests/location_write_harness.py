"""Diagnostic harness for #73: compares different approaches to
recording a car's `location` once parked.

Measures failure RATE across many reps per approach rather than a
single pass/fail. Deliberately NOT a pytest test (no @pytest.mark.live
here, not collected by the normal suite) -- this is a comparison tool,
not a regression gate. Run directly:

    uv run python tests/location_write_harness.py --approach baseline --reps 10

Isolates just the write-formatting step itself (see tests/data/scenarios/
location_write_isolated/scenario.yaml: one car, one already-resolvable
parking event, one spot) -- separate from arrival-order reasoning
(tests/test_human_validated/test_race_placement_live.py) or
driving/parking separation (test_parking_split_live.py in that same
package), which are already covered elsewhere.

Three approaches are compared: "baseline" (today's direct single-shot
update_registry write), "confirm" (#74's opt-in preview=True /
confirm_token round trip -- write, review what it's about to commit
against what's already there, then confirm or correct BEFORE committing),
and "consolidate" (#76's post-write alternative -- write normally, then
call consolidate_review to see everything recorded so far and fix
anything wrong AFTER committing). All three share the same run/
measurement machinery below; only the instruction text differs.

#83: every rep also records which component type(s) car_a actually got
written to beyond what a correct run produces (_EXPECTED_CAR_A_COMPONENTS)
-- e.g. `parent` instead of `location` -- so a run's printed summary names
what a wrong write actually contained, not just that `location` came up
empty. Collected on every rep, not just failures, since an unexpected
component alongside a PASS is itself worth seeing.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from collections import Counter

from test_human_validated.helpers import LOW_QUALITY_MODEL, HeadlessSession, _load_registrar, _parked_at
from emc2p.testing.registry_checks import unexpected_components

REPO_ROOT = Path(__file__).parent.parent
SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "location_write_isolated"

# scripts/ isn't a package (no __init__.py, deliberately) -- so this is a
# plain sys.path addition rather than a normal import.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from get_usage import get_usage  # noqa: E402


def _snapshot_usage(label: str) -> dict | None:
    """Best-effort /usage snapshot -- see scripts/get_usage.py.

    Usage tracking is auxiliary instrumentation, not something a test run's
    success should ever hinge on: it spawns a whole nested interactive
    claude session, which can fail for reasons that have nothing to do with
    whether the harness itself works (no claude CLI, no PTY in this
    environment, a slow/absent MCP handshake, ...). Any failure here is
    swallowed and reported, not raised -- the reps loop always runs either way.
    """
    try:
        return get_usage()
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see docstring
        print(f"[usage] could not capture usage snapshot ({label}): {exc}", file=sys.stderr)
        return None

# The scenario seed's own starting components (object, description) plus
# `location`, the one thing a correct run is supposed to add to car_a.
_EXPECTED_CAR_A_COMPONENTS = {"object", "description", "location"}

# Today's only approach: the model composes and writes correctly-formatted
# entity-first YAML directly via update_registry.
_BASELINE_INSTRUCTION = (
    "Call advance_simulation and answer its prompts (resolve, then plan) until its "
    "status is \"done\" -- there is only one event. Record via update_registry that "
    "car_a parked in parking_spot_1, plus car_a_park's own outcome and event_state. "
    "Don't narrate anything back to me."
)

# #74's preview/confirm alternative: write with preview=True first,
# check the returned review against what was intended before confirming.
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

# #76's post-write alternative: write normally (no confirmation step),
# then call consolidate_review to see everything and fix anything wrong.
_CONSOLIDATE_INSTRUCTION = (
    "Call advance_simulation and answer its prompts (resolve, then plan) until its "
    "status is \"done\" -- there is only one event. Record via update_registry that "
    "car_a parked in parking_spot_1, plus car_a_park's own outcome and event_state. "
    "Then call consolidate_review to see everything recorded so far, and check it "
    "against what you actually intended to record. If you notice anything wrong -- the "
    "same fact recorded under the wrong or an invented component name -- fix it with a "
    "follow-up update_registry call. Don't narrate anything back to me."
)

_APPROACHES = {
    "baseline": _BASELINE_INSTRUCTION,
    "confirm": _CONFIRM_INSTRUCTION,
    "consolidate": _CONSOLIDATE_INSTRUCTION,
}


def run_one(approach: str, tmp_dir: Path, model: str = LOW_QUALITY_MODEL) -> tuple[bool, str, dict, set[str]]:
    """One rep: opens a fresh world, asks the model to record car_a's
    location under the given approach.

    Returns (success, narration, usage, misfires) -- narration kept for
    diagnosing failures after the fact, not just the pass/fail count;
    usage (see HeadlessSession.usage_summary) kept so #75's cost
    comparison isn't limited to whichever approach happens to get run
    last; misfires (see unexpected_components) names which component(s)
    car_a actually got written to beyond what a correct run produces --
    #83, collected every rep (not just failures) since a false positive
    here is itself useful signal. `model` defaults to this harness's
    usual weak-model target, but #85 needs a stronger-model comparison
    point (Sonnet vs. Haiku spend on the identical task) -- see --model.
    """
    save_dir = tmp_dir / "save"
    instruction = _APPROACHES[approach]
    # This harness compares how the *connected* model performs a write
    # under each approach -- explicit override of the keyed_subagent default.
    with HeadlessSession(save_dir, model=model, responder="host") as session:
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={SCENARIO_DIR} "
            f"to open a story-simulator world. Then {instruction}"
        )
        try:
            r = _load_registrar(save_dir, narration)
            success = _parked_at(r.get_current_value("location", alias="car_a"), "parking_spot_1")
            misfires = unexpected_components(r, "car_a", _EXPECTED_CAR_A_COMPONENTS)
        except AssertionError as exc:
            # _load_registrar's own assertion: the model never actually called
            # start_world -- a rep outcome to count, not a harness bug.
            success = False
            misfires = set()
            narration = f"{narration}\n\n[harness: {exc}]"
        return success, narration, session.usage_summary(), misfires


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approach", choices=sorted(_APPROACHES), default="baseline")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--model", default=LOW_QUALITY_MODEL, help="claude -p --model value, e.g. claude-sonnet-5")
    args = parser.parse_args()

    usage_before = _snapshot_usage("before")

    successes = 0
    failures: list[str] = []
    misfire_tally: Counter[str] = Counter()
    total_cost_usd = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_api_ms = 0
    for i in range(args.reps):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                ok, narration, usage, misfires = run_one(args.approach, Path(tmp), model=args.model)
            except KeyboardInterrupt:
                raise
            except BaseException as exc:
                # Anything run_one doesn't already turn into a normal (False, ...)
                # result, e.g. HeadlessSession's own timeout/crash handling.
                ok = False
                narration = f"[harness error: {exc!r}]"
                usage = {
                    "total_cost_usd": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "duration_api_ms": 0,
                }
                misfires = set()
            successes += ok
            total_cost_usd += usage["total_cost_usd"]
            total_input_tokens += usage["input_tokens"]
            total_output_tokens += usage["output_tokens"]
            total_duration_api_ms += usage["duration_api_ms"]
            misfire_tally.update(misfires)
            misfire_note = f" [wrote: {', '.join(sorted(misfires))}]" if misfires else ""
            print(
                f"[{args.approach}/{args.model}] rep {i + 1}/{args.reps}: {'PASS' if ok else 'FAIL'} "
                f"(${usage['total_cost_usd']:.4f}, {usage['duration_api_ms'] / 1000:.1f}s active)"
                f"{misfire_note}"
            )
            if not ok:
                failures.append(narration)

    rate = successes / args.reps
    print(f"\n[{args.approach}/{args.model}] {successes}/{args.reps} = {rate:.0%}")
    print(
        f"[{args.approach}/{args.model}] total: ${total_cost_usd:.4f}, "
        f"{total_input_tokens} input tokens, {total_output_tokens} output tokens, "
        f"{total_duration_api_ms / 1000:.1f}s active API time "
        f"(${total_cost_usd / args.reps:.4f}/rep, {total_duration_api_ms / 1000 / args.reps:.1f}s/rep)"
    )
    if misfire_tally:
        print(f"[{args.approach}/{args.model}] unexpected components written (any rep): {dict(misfire_tally)}")
    if failures:
        print("\nFailure narrations:")
        for n in failures:
            print(f"  - {n!r}")

    usage_after = _snapshot_usage("after")
    if usage_before is not None and usage_after is not None:
        session_delta = usage_after["session_pct_used"] - usage_before["session_pct_used"]
        week_delta = usage_after["week_pct_used"] - usage_before["week_pct_used"]
        print(
            f"\n[{args.approach}/{args.model}] usage before: "
            f"session {usage_before['session_pct_used']}%, week {usage_before['week_pct_used']}%"
        )
        print(
            f"[{args.approach}/{args.model}] usage after:  "
            f"session {usage_after['session_pct_used']}%, week {usage_after['week_pct_used']}%"
        )
        print(
            f"[{args.approach}/{args.model}] usage delta:  "
            f"session +{session_delta}pp, week +{week_delta}pp over {args.reps} reps"
        )
    else:
        print(f"\n[{args.approach}/{args.model}] usage tracking unavailable for this run (see warnings above)")


if __name__ == "__main__":
    main()
