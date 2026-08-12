"""Deterministic sibling to tests/test_human_validated.py::test_car_parking_core_sim.

Drives the same real scenario (tests/data/scenarios/parking) through the
same advance_simulation/update_registry mechanism, but in-process with
hand-written "perfect" answers instead of a live model over a `claude -p`
subprocess -- no LLM, no MCP round-trip, no cost, no flakiness. This
exists to separate two different failure modes that look identical from
the live test alone: the *system* doing something wrong (event ordering,
prompt text, resume_token bookkeeping, a write not reading back) versus
the *model* reasoning about a correct system incorrectly. Everything
asserted here is exact -- prompt text, due-order, and registry state --
so a live-test failure can be checked against this first: if this test
still passes, the mechanism is sound and the live failure is the model;
if this test fails too, it's a real bug independent of any model at all.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from iacs.registrar import Registrar
from story_simulator.config import registry_url
from story_simulator.core import safe_view_current
from story_simulator.mcp_server import advance_simulation, start_world, update_registry

REPO_ROOT = Path(__file__).parent.parent
PARKING_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking"

_HOST_FRAMING = (
    "Decide the answer yourself, standing in for whichever role this call "
    "needs (a player's own absent character, an NPC, a base-module entity "
    "that's come due, ...) -- don't wait for input and don't hand this off."
)


def _make_ctx():
    ctx = MagicMock()
    ctx.request_context.session = MagicMock()
    return ctx


def _location(save_dir, alias: str) -> str | None:
    """Read `alias`'s current location.value directly from the registry --
    the same read path (view_current on a time_dimension'd component) a
    live test failure needs cross-checking against. Deliberately
    self-contained (hand-filters by alias here rather than using the
    registry's own `aliases` view param -- see task #36) so this test
    doesn't depend on an iacs change still waiting on its own PR merge.
    """
    registrar = Registrar.load(registry_url(save_dir))
    df = safe_view_current(registrar, "location.value")
    if df is None:
        return None
    match = df[df["entity_id.alias"] == alias]
    return None if match.empty else str(match.iloc[-1]["location.value"])


def _resolve_prompt(alias: str) -> str:
    return (
        f"{_HOST_FRAMING}\n\n"
        f"{alias} is due. Look up whatever you need (view_entity/"
        f"view_registry, including its involved_entity links) to work "
        f"out what happens, then record it: {alias}'s own outcome, "
        f"{alias}'s own event_state (complete if this fully resolves "
        f"it, interrupted if something cuts it short), and anything it "
        f"changes about the entities it involves -- write those changes "
        f"directly onto each affected entity itself (e.g. a `location` "
        f"or `state` component on it), not only described in {alias}'s "
        f"own outcome text -- all via update_registry."
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
    outcome/event_state, and the car's own location -- exactly what a
    correct responder is asked to do, matching the puzzle's known-correct
    solution (see this scenario's own description.value)."""
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
        ctx,
    )


def test_due_order_matches_true_arrival_order(tmp_path):
    """car_b_trip (due at 1020) must be served before car_c_trip (due at
    1080) before car_a_trip (due at 1800) -- computed straight from the
    scenario's own start_time+duration, not trusted from prose. This is
    exactly the ordering the user was skeptical of when reading the live
    trace; pinned down here independent of any model."""
    ctx = _make_ctx()
    save_dir = tmp_path / "save"
    start_world(str(save_dir), ctx, scenario_dir=str(PARKING_SCENARIO_DIR))

    result = asyncio.run(advance_simulation(ctx))
    assert result["status"] == "input_required"
    assert result["prompt"] == _resolve_prompt("car_b_trip")


def test_full_walkthrough_exact_prompts_and_registry_state(tmp_path):
    """Drives all three events to completion with predetermined correct
    answers, asserting the exact prompt text and exact resulting registry
    state at every step -- not just substrings."""
    ctx = _make_ctx()
    save_dir = tmp_path / "save"
    start_world(str(save_dir), ctx, scenario_dir=str(PARKING_SCENARIO_DIR))

    plan = [
        ("car_b_trip", "car_b", "parked in parking_spot_1"),
        ("car_c_trip", "car_c", "parked in parking_spot_2"),
        ("car_a_trip", "car_a", "parked on the street"),
    ]

    result = asyncio.run(advance_simulation(ctx))
    for event_alias, car_alias, location in plan:
        assert result["status"] == "input_required"
        assert result["prompt"] == _resolve_prompt(event_alias)
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
    for event_alias, car_alias, location in plan:
        assert _location(save_dir, car_alias) == location
