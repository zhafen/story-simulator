"""Deterministic sibling to the live human-validated tests
(tests/test_human_validated/).

Drives the same real scenario (tests/data/scenarios/parking) through the
same advance_simulation/update_registry mechanism, but in-process with
hand-written "perfect" answers instead of a live model over a `claude -p`
subprocess -- no LLM, no MCP round-trip, no cost, no flakiness. This
exists to separate two different failure modes that look identical from
the live test alone: the *system* doing something wrong (event ordering,
prompt text, resume_token bookkeeping, a write not reading back) versus
the *model* reasoning about a correct system incorrectly. Everything
asserted here is exact -- prompt text, end_time-order, and registry state --
so a live-test failure can be checked against this first: if this test
still passes, the mechanism is sound and the live failure is the model;
if this test fails too, it's a real bug independent of any model at all.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from emc2p.registrar import Registrar
from story_simulator.config import registry_url
from story_simulator.core import safe_view_current
from story_simulator.mcp_server import advance_simulation, start_world, update_registry

REPO_ROOT = Path(__file__).parent.parent.parent
PARKING_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking"

_HOST_FRAMING = (
    "Decide the answer yourself, standing in for whichever role this call "
    "needs (a player's own absent character, an NPC, a base-module entity "
    "whose end_time has been reached, ...) -- don't wait for input and "
    "don't hand this off."
)


def _make_ctx():
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


def _location(save_dir, alias: str) -> str | None:
    """Read `alias`'s current location.value directly from the registry.

    Same read path (view_current on a time_dimension'd component) a
    live test failure needs cross-checking against. Deliberately
    self-contained (hand-filters by alias here rather than
    using the registry's own `aliases` view param -- see task #36) so
    this test doesn't depend on an iacs change still waiting on its own
    PR merge.
    """
    registrar = Registrar.load(registry_url(save_dir))
    df = safe_view_current(registrar, "location.value")
    if df is None:
        return None
    match = df[df["entity_id.alias"] == alias]
    return None if match.empty else str(match.iloc[-1]["location.value"])


def _resolve_prompt(alias: str, end_time: float) -> str:
    return (
        f"{_HOST_FRAMING}\n\n"
        f"{alias}'s end_time (world time {end_time:g}) has been reached. "
        f"Nothing else with an earlier end_time is still unresolved -- if "
        f"another entity's own event hasn't reached event_state: complete "
        f"yet (check via view_entity/view_registry, not assumed from its "
        f"start_time or where it appears in a table), treat it as not "
        f"having happened yet. Look up whatever you need (view_entity/"
        f"view_registry, including its involved_entity links) to work out "
        f"what happens, then "
        f"record it: {alias}'s own "
        f"outcome, {alias}'s own event_state (complete if this fully "
        f"resolves it, interrupted if something cuts it short), and "
        f"anything it changes about the entities it involves -- write "
        f"those changes directly onto each affected entity itself, using "
        f"whichever component type actually fits (view_entity on the "
        f"component type's own name, e.g. view_entity('location'), shows "
        f"its field descriptions if you're unsure which one or how to "
        f"phrase it), not only described in {alias}'s own outcome text -- "
        f"all via update_registry."
    )


def _plan_prompt(alias: str) -> str:
    return (
        f"{_HOST_FRAMING}\n\n"
        f"Given how {alias} just resolved, does anything new need to "
        f"happen as a result? If so, create it now: one or more new "
        f"event entities (their own start_time/duration/event_state/"
        f"involved_entity) via update_registry. If nothing follows "
        f"from this, just say so -- no new events needed."
    )


def _mark_resolved(ctx, event_alias: str, car_alias: str, location: str) -> None:
    """The "perfect" answer to a resolve prompt: record the event's own
    outcome/event_state, and the car's own location.

    Exactly what a correct responder is asked to do, matching the
    puzzle's known-correct solution (see this scenario's own description.value).
    """
    update_registry(
        f"{event_alias}:\n"
        f"    - outcome:\n"
        f"        value: {event_alias} resolved -- {car_alias} {location}.\n"
        f"    - event_state:\n"
        f"        value: complete\n"
        f"\n"
        f"{car_alias}:\n"
        f"    - location:\n"
        f"        value: {location}\n",
        ctx=ctx,
    )


def test_end_time_order_matches_true_arrival_order(tmp_path):
    """car_b_trip (end_time 1020) must be served before car_c_trip
    (end_time 1080) before car_a_trip (end_time 1800).

    Computed straight from the scenario's own start_time+duration, not
    trusted from prose -- exactly the ordering the user was skeptical
    of when reading the live trace, pinned down here independent of any model.
    """
    ctx = _make_ctx()
    save_dir = tmp_path / "save"
    start_world(str(save_dir), ctx, scenario_dir=str(PARKING_SCENARIO_DIR))

    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["prompt"] == _resolve_prompt("car_b_trip", end_time=1020)


def test_full_walkthrough_exact_prompts_and_registry_state(tmp_path):
    """Drives all three events to completion with predetermined correct
    answers, asserting the exact prompt text and registry state at every step."""
    ctx = _make_ctx()
    save_dir = tmp_path / "save"
    start_world(str(save_dir), ctx, scenario_dir=str(PARKING_SCENARIO_DIR))

    plan = [
        ("car_b_trip", "car_b", "parked in parking_spot_1", 1020),
        ("car_c_trip", "car_c", "parked in parking_spot_2", 1080),
        ("car_a_trip", "car_a", "parked on the street", 1800),
    ]

    result = asyncio.run(advance_simulation(ctx))
    for event_alias, car_alias, location, end_time in plan:
        assert result["status"] == "input_required"
        assert result["prompt"] == _resolve_prompt(event_alias, end_time)
        assert result["responder"] == "host"

        _mark_resolved(ctx, event_alias, car_alias, location)
        assert _location(save_dir, car_alias) == location, (
            f"{car_alias}.location should read back exactly what was just "
            f"written -- if this fails, update_registry's write didn't "
            f"actually persist/read back, independent of anything a model "
            f"decided"
        )

        result = asyncio.run(
            advance_simulation(ctx, resume_token=result["resume_token"], answer=f"{event_alias} resolved.")
        )
        assert result["status"] == "input_required"
        assert result["prompt"] == _plan_prompt(event_alias)

        result = asyncio.run(
            advance_simulation(ctx, resume_token=result["resume_token"], answer="No new events needed.")
        )

    assert result == {"status": "done", "narration": "Nothing scheduled."}

    # Final state: every car ended up exactly where the puzzle says it should.
    for event_alias, car_alias, location, end_time in plan:
        assert _location(save_dir, car_alias) == location
