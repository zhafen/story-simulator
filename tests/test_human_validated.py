"""Live end-to-end tests that drive story-simulator-mcp through a real MCP client.

There is no in-process narrator to call directly (see
docs/manifest/history.yaml: project_history.turn_pipeline_removed), so this
spawns `claude -p` as a real subprocess against this repo's .mcp.json,
exactly the way the README's quick-start describes a client connecting.

Written for the current base event loop only (no character/NPC module --
see docs/architecture.md and CLAUDE.md's shelving note): every entity here
is a plain object, `advance_simulation` always resolves a due entity via
responder="host" (`story_simulator.config.event_responder`'s default), and
the connected agent is expected to decide each entity's outcome itself,
looking up whatever it needs via view_registry/view_entity, exactly as the
server's own tool instructions describe. The character-module-era tests
that used to live in this file (NPC/move scenarios, HeadlessSession, ...)
are preserved at shelved/tests/test_human_validated.py, dormant until that
module is un-shelved.
"""

import json
import shutil
import subprocess
from pathlib import Path

import ibis
import pytest

from iacs.registrar import Registrar
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn

REPO_ROOT = Path(__file__).parent.parent
PARKING_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking"

# Cheapest available model. Kept deliberately weak rather than swapped for a
# stronger one: story-simulator's tools need to hold up under a bad model's
# mistakes, not just a good one's, so that's the model these tests exercise.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# Bash/Task are explicitly denied everywhere below, not just left off the
# allowlist: a weak model, given the choice, sometimes reaches for "write a
# Python script that calls these functions directly" instead of just calling
# the MCP tools it already has -- confirmed happening in practice -- and an
# unapproved Bash call in headless mode doesn't fail fast, it sits waiting
# for an approval that never comes. Denying it outright removes the option
# instead of hoping the model doesn't reach for it.
_MCP_TOOL_ARGS = [
    "--mcp-config",
    ".mcp.json",
    "--strict-mcp-config",
    "--allowedTools",
    "mcp__story-simulator__*",
    "mcp__iacs__*",
    "--disallowedTools",
    "Bash",
    "Task",
]


def _run_headless_turn(prompt: str, *, model: str = LOW_QUALITY_MODEL, timeout: int = 180) -> str:
    """Run one single-shot headless `claude -p` turn against this repo's MCP servers.

    One prompt in, one reply out, then the process exits. A single turn is
    enough even for a multi-step advance_simulation loop: each
    input_required/resume_token round trip is an ordinary nested tool call
    within that one turn (MRTR, MCP spec 2026-07-28), not a separate user
    message.
    """
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not on PATH")

    result = subprocess.run(
        ["claude", "-p", prompt, *_MCP_TOOL_ARGS, "--model", model, "--output-format", "json"],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, f"claude exited {result.returncode}: {result.stderr}"
    payload = json.loads(result.stdout)
    assert not payload["is_error"], payload
    return payload["result"]


def _load_registrar(save_dir: Path, narration: str) -> Registrar:
    """Confirm `save_dir`'s schema actually exists, then load it.

    A weak model can narrate a plausible-sounding scene without ever
    calling `start_world` -- or call it with a subtly wrong `save_dir` it
    mistyped out of the prompt's text, confirmed happening in practice --
    so this checks the schema was actually created for the exact `save_dir`
    the test used before reading it, rather than either silently reading
    whichever schema the connection falls through to when the named one
    doesn't exist (see `config.registry_url`'s docstring) or hitting a
    confusing raw `ibis` error partway through `Registry.from_database`'s
    table enumeration. `list_databases` is `ibis`'s own, backend-agnostic
    name for this -- for the current Postgres backend that means schemas,
    but the call itself doesn't hardcode that.
    """
    schema = registry_schema_name(save_dir)
    base_con = ibis.connect(resolve_database_dsn())
    assert schema in base_con.list_databases(), (
        f"No registry schema exists for {save_dir} -- start_world was not "
        f"actually called for this exact save_dir despite this "
        f"narration: {narration!r}"
    )
    return Registrar.load(registry_url(save_dir))


def _distance(registrar: Registrar, alias_a: str, alias_b: str) -> float:
    """Euclidean distance between two aliased entities' current positions.

    A small local stand-in for the character module's own
    `story_simulator.spatial.distance` (now shelved along with the rest of
    that file) -- this test needs nothing fancier than a flat (x, y) read.
    """
    positions = registrar.view_current(["position.x", "position.y"]).execute()

    def _point(alias: str) -> tuple[float, float]:
        row = positions[positions["entity_id.alias"] == alias].iloc[0]
        return float(row["position.x"]), float(row["position.y"])

    ax, ay = _point(alias_a)
    bx, by = _point(alias_b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


@pytest.mark.live
@pytest.mark.skip(
    reason="Not yet attempted -- tracks a reasoning capability the core simulation "
    "doesn't reliably have yet (working out cross-entity scheduling from raw "
    "facts, rather than reacting to whatever order advance_simulation happens "
    "to process entities in). Un-skip once that's actually been built and this "
    "passes for real, rather than loosening the assertions to fit whatever the "
    "sim currently does."
)
def test_car_parking_reasoning(tmp_path):
    """Three cars must work out their own arrival order from raw facts, then
    correctly divide up a two-spot parking lot on a first-come-first-served basis.

    This is a human-validated check on "reasoning, not physics" (see CLAUDE.md's
    component-schema section and the project's general design goals): nothing
    about the scenario needs distance, speed, or any other physical-world fact
    the sim would have to invent or look up -- every number the puzzle needs
    (each car's start delay and trip duration) is stated directly in that
    car's own `description` (see tests/data/scenarios/parking/scenario.yaml).
    What's actually hard is the arithmetic and the resource bookkeeping: Car A
    starts driving first but has the longest trip and so actually arrives
    last; Car B starts second with a slightly longer trip than Car C but,
    because it left earlier by more than that difference, still arrives
    first; Car C starts last with the shortest trip and arrives second.
    First-come-first-served over exactly two dedicated spots then means Car B
    takes parking_spot_1, Car C takes parking_spot_2, and Car A -- last to
    arrive -- has to park on the street.

    Deliberately structured so naive shortcuts give the wrong answer: "first
    to start goes first" and "shortest trip wins" both misorder these three,
    and the scenario's own `next_due` seeding (see that file's docstring)
    even makes advance_simulation *pop* the cars in start order (A, B, C) --
    matching neither the real arrival order nor the parking outcome -- so
    getting this right takes actually reasoning through the elapsed-time
    arithmetic each car's own description gives it, not just following
    processing order.

    No character/NPC module is involved (see this file's own module
    docstring): every entity is a plain object, and each of the three "X is
    due" prompts advance_simulation raises is answered by the connected
    agent itself (responder="host"), which has to call view_entity/
    view_registry on its own to learn the puzzle facts before deciding —
    exactly the pattern story-simulator's own tool instructions describe.
    One headless turn is enough since every one of those round trips is a
    nested tool call within that single turn, not a separate user message.
    A generous timeout accounts for three such rounds.
    """
    ROUGHLY_THERE = 15.0
    save_dir = tmp_path / "test_save"

    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} and scenario_dir={PARKING_SCENARIO_DIR} "
        "to open a story-simulator world. Then call advance_simulation repeatedly. Each "
        "time it comes back with status \"input_required\", it's naming one entity that's "
        "now due -- look up whatever you need with view_registry/view_entity, decide what "
        "happens, record it with update_registry, and call advance_simulation again with "
        "that exact resume_token and your answer (ending with a `next_due_in: <seconds>` "
        "line if that entity has more to do, or omitting it if it's finished) -- until "
        "advance_simulation's status is \"done\". There is no human player and no subagent "
        "to delegate to here; decide everything yourself. Don't narrate anything back to "
        "me; just drive the simulation to completion and stop.",
        timeout=300,
    )

    r = _load_registrar(save_dir, narration)
    assert _distance(r, "car_a", "street") < ROUGHLY_THERE, (
        "Car A starts first but has the longest trip, so it should actually "
        f"arrive last and end up parked on the street -- narration: {narration!r}"
    )
    assert _distance(r, "car_b", "parking_spot_1") < ROUGHLY_THERE, (
        "Car B's trip is slightly longer than Car C's, but it starts earlier by "
        "more than that difference, so it should still arrive first and take "
        f"the first parking spot -- narration: {narration!r}"
    )
    assert _distance(r, "car_c", "parking_spot_2") < ROUGHLY_THERE, (
        "Car C starts last with the shortest trip and should arrive second, "
        f"taking the remaining parking spot -- narration: {narration!r}"
    )
