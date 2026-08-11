"""Live end-to-end tests that drive story-simulator-mcp through a real MCP client.

There is no in-process narrator to call directly (see
docs/manifest/history.yaml: project_history.turn_pipeline_removed), so this
spawns `claude -p` as a real subprocess against this repo's .mcp.json,
exactly the way the README's quick-start describes a client connecting.

Written for the current event-entity simulation loop (no character/NPC
module -- see docs/architecture.md and CLAUDE.md's shelving note): world
state is `event` entities, each due once world time reaches its own
start_time + duration, and every due event resolves via two separate
responder calls (resolve, then plan) at responder="host"
(`story_simulator.config.event_responder`'s default). The connected agent
is expected to decide each step itself, looking up whatever it needs via
view_registry/view_entity and recording its own decisions via
update_registry, exactly as the server's own tool instructions describe.

Uses `HeadlessSession` (one persistent `claude -p` process over
stream-json, several `send_turn` calls) rather than a single one-shot
turn, so the test itself can pace the simulation one event at a time and
check registry state between each -- not just the final result. The
character-module-era tests that used to live in this file (NPC/move
scenarios, an earlier version of this same class) are preserved at
shelved/tests/test_human_validated.py, dormant until that module is
un-shelved.
"""

import json
import selectors
import shutil
import subprocess
import time
from pathlib import Path

import ibis
import pytest

from iacs.registrar import Registrar
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn
from story_simulator.core import safe_view_current

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


class HeadlessSession:
    """One continuously-running `claude -p` process, driven over stream-json.

    Unlike separate one-shot calls, this keeps a single story-simulator-mcp
    child process (and its Postgres connection) alive for the whole `with`
    block, so `send_turn`'s caller can read the registry in between turns
    while that process is still holding it open, and so the test itself
    can pace the conversation -- one event's worth of work per turn --
    rather than handing the model a single "drive it all the way" prompt
    with no chance to inspect state along the way.
    """

    def __init__(self, *, model: str = LOW_QUALITY_MODEL, turn_timeout: float = 240):
        self.model = model
        self.turn_timeout = turn_timeout
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "HeadlessSession":
        if shutil.which("claude") is None:
            pytest.skip("claude CLI not on PATH")
        self.proc = subprocess.Popen(
            [
                "claude",
                "-p",
                "--input-format",
                "stream-json",
                "--output-format",
                "stream-json",
                "--verbose",
                *_MCP_TOOL_ARGS,
                "--model",
                self.model,
            ],
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return self

    def send_turn(self, prompt: str) -> str:
        """Send one prompt on the ongoing conversation and block for its narrated reply."""
        assert self.proc is not None and self.proc.stdin is not None
        message = {"type": "user", "message": {"role": "user", "content": prompt}}
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

        sel = selectors.DefaultSelector()
        sel.register(self.proc.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + self.turn_timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._fail(f"turn timed out after {self.turn_timeout}s waiting for a reply")
                if not sel.select(timeout=remaining):
                    continue
                line = self.proc.stdout.readline()
                if not line:
                    self._fail("claude process exited before replying")
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "result":
                    if event.get("is_error"):
                        self._fail(f"turn errored: {event}")
                    return event["result"]
        finally:
            sel.close()

    def _fail(self, message: str) -> None:
        stderr = self.proc.stderr.read() if self.proc and self.proc.stderr else ""
        self.close()
        pytest.fail(f"{message}\nstderr: {stderr}")

    def close(self) -> None:
        if self.proc is None:
            return
        proc, self.proc = self.proc, None
        if proc.stdin:
            proc.stdin.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()

    def __exit__(self, *exc_info) -> None:
        self.close()


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


def _location(registrar: Registrar, alias: str) -> str | None:
    """The current `location.value` recorded for an aliased entity, or
    None if it has none yet. `location` is a declared, time_dimension'd
    component type (see manifest/builtins.yaml), so this resolves the
    current row per entity rather than assuming a single write.
    """
    df = safe_view_current(registrar, "location.value")
    if df is None:
        return None
    match = df[df["entity_id.alias"] == alias]
    return None if match.empty else str(match.iloc[-1]["location.value"])


def _event_states(registrar: Registrar) -> dict[str, str]:
    """Map of {event_alias: current event_state.value}, or {} if nothing's been recorded yet."""
    df = safe_view_current(registrar, "event_state.value")
    if df is None:
        return {}
    return dict(zip(df["entity_id.alias"], df["event_state.value"]))


# One turn's instruction, reused for each of the three events: resolve
# advance_simulation's two prompts for exactly one event (its resolve
# step, then its plan step), then stop before touching a second one. The
# "no human/subagent behind this, decide yourself" framing doesn't need
# repeating here -- advance_simulation's own input_required prompt
# already says that for whichever responder it names (see
# resolve._frame_for_responder) -- so this only states the pacing this
# test specifically needs, which nothing else knows to enforce.
#
# The "decide the full outcome now" sentence below is here, not in the
# scenario or in core.py's general prompts, for the same reason: it's a
# pacing constraint specific to how *this test* checks state turn by
# turn, not a rule real gameplay should follow (a real event may well
# legitimately want to defer part of itself to a follow-up). Confirmed
# live as necessary -- a weak model, left to its own judgment, sometimes
# resolves "drive to restaurant and search for parking" as "arrived,
# still searching" and defers the actual parking assignment to a new
# event it schedules in the plan step, which this test's single-turn
# assertions have no way to see coming.
_RESOLVE_ONE_EVENT_INSTRUCTION = (
    "Call advance_simulation. Answer its first prompt (resolving the next due event -- "
    "look up whatever you need and record the outcome via update_registry). Decide the "
    "full outcome now, in this one turn -- don't defer part of it (e.g. a still-pending "
    "sub-decision like where exactly something ends up) to a new event in the next prompt. "
    "Then answer its second prompt for that same event (planning any follow-up, or saying "
    "none is needed) -- two separate advance_simulation calls for the one event. Once both "
    "are answered, stop: do not call advance_simulation a third time. Don't narrate "
    "anything back to me."
)


@pytest.mark.live
def test_car_parking_core_sim(tmp_path):
    """Three cars must work out their own arrival order from raw facts, then
    correctly divide up a two-spot parking lot on a first-come-first-served basis --
    checked one event at a time, not just by the final result.

    Car A starts driving first but has the longest trip and so actually
    arrives last; Car B starts second with a slightly longer trip than Car
    C but, because it left earlier by more than that difference, still
    arrives first; Car C starts last with the shortest trip and arrives
    second. First-come-first-served over exactly two dedicated spots then
    means Car B takes parking_spot_1, Car C takes parking_spot_2, and Car
    A -- last to arrive -- has to park on the street.

    Each car has exactly one pre-planned `event` entity (car_X_trip, see
    tests/data/scenarios/parking/scenario.yaml) whose start_time + duration
    already *is* its true arrival time -- so pop_event's own mechanical
    sort (soonest due first) pops them in the real arrival order (B, C,
    A), not start order or trip length. That's what makes each event's own
    resolution answerable with "very basic reasoning": by the time any one
    event resolves, whichever spots earlier events already claimed
    (recorded on the relevant car's own `location`) are genuinely already
    claimed, not a guess about entities that haven't been touched yet.

    This test checks that directly, turn by turn: after each event
    resolves, the car it concerned should have its final `location`
    recorded, and -- just as importantly -- the cars whose events haven't
    come due yet should still show no location at all. Getting the *order*
    right is exactly what a naive shortcut (start order, or trip length)
    would get wrong, so a passing intermediate check after each turn is
    real evidence the loop -- not a lucky final state -- is doing this
    correctly.
    """
    save_dir = tmp_path / "test_save"

    with HeadlessSession() as session:
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={PARKING_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RESOLVE_ONE_EVENT_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)
        assert _location(r, "car_b") == "parked in parking_spot_1", (
            "Car B should be first to actually arrive (it left earlier than Car C by more "
            f"than their trip-length difference) and take the first spot -- narration: {narration!r}"
        )
        assert _location(r, "car_c") is None and _location(r, "car_a") is None, (
            "Only one event should have resolved this turn -- car_c's and car_a's own events "
            f"haven't come due yet, so neither should have a recorded location -- narration: {narration!r}"
        )
        states = _event_states(r)
        assert states.get("car_b_trip") == "complete", states
        assert states.get("car_c_trip") != "complete" and states.get("car_a_trip") != "complete", states

        narration = session.send_turn(f"Again, {_RESOLVE_ONE_EVENT_INSTRUCTION}")
        r = _load_registrar(save_dir, narration)
        assert _location(r, "car_c") == "parked in parking_spot_2", (
            "Car C should be second to arrive (after Car B, before Car A) and take the "
            f"remaining dedicated spot -- narration: {narration!r}"
        )
        assert _location(r, "car_a") is None, (
            "Car A's own event still hasn't come due yet, so it shouldn't have a recorded "
            f"location -- narration: {narration!r}"
        )
        assert _location(r, "car_b") == "parked in parking_spot_1", (
            f"Car B's already-recorded outcome shouldn't change -- narration: {narration!r}"
        )
        states = _event_states(r)
        assert states.get("car_c_trip") == "complete", states
        assert states.get("car_a_trip") != "complete", states

        narration = session.send_turn(
            "Call advance_simulation again and keep answering its prompts (resolve, then "
            "plan, for whatever event it names) until its status is \"done\" -- there's only "
            "one event left. Don't narrate anything back to me."
        )
        r = _load_registrar(save_dir, narration)
        assert _location(r, "car_a") == "parked on street", (
            "Car A starts first but has the longest trip, so it should actually arrive last "
            f"and end up parked on the street -- narration: {narration!r}"
        )
        assert _location(r, "car_b") == "parked in parking_spot_1", (
            f"Car B's already-recorded outcome shouldn't change -- narration: {narration!r}"
        )
        assert _location(r, "car_c") == "parked in parking_spot_2", (
            f"Car C's already-recorded outcome shouldn't change -- narration: {narration!r}"
        )
