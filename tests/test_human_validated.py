"""Live end-to-end tests that drive story-simulator-mcp through a real MCP client.

There is no in-process narrator to call directly (see
docs/manifest/history.yaml: project_history.turn_pipeline_removed), so this
spawns `claude -p` as a real subprocess against this repo's .mcp.json,
exactly the way the README's quick-start describes a client connecting.

Written for the current event-entity simulation loop (no character/NPC
module -- see docs/architecture.md and CLAUDE.md's shelving note): world
state is `event` entities, each ready to resolve once world time reaches
its own end_time (start_time + duration), and every such event resolves via two separate
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
import os
import selectors
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import ibis
import pytest

from iacs.registrar import Registrar
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn
from story_simulator.core import safe_view_current

REPO_ROOT = Path(__file__).parent.parent
PARKING_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "parking"

# Every raw stream-json line from a HeadlessSession's `claude -p` subprocess
# lands here, one file per session -- not just the final narrated result.
# Diagnosing the live-test flakiness previously required hand-rolling a
# throwaway script outside the test suite to capture this (thinking blocks,
# tool_use/tool_result payloads, intermediate assistant messages) since
# HeadlessSession.send_turn only ever returned the final "result" event's
# text. Gitignored -- these are per-run debug artifacts, not source.
LIVE_TRACE_DIR = REPO_ROOT / ".live_test_traces"

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

    def __init__(self, save_dir: Path, *, model: str = LOW_QUALITY_MODEL, turn_timeout: float = 240):
        self.save_dir = save_dir
        self.model = model
        self.turn_timeout = turn_timeout
        self.proc: subprocess.Popen | None = None
        LIVE_TRACE_DIR.mkdir(exist_ok=True)
        self.trace_path = (
            LIVE_TRACE_DIR / f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}.jsonl"
        )
        self._trace_file = None

    def __enter__(self) -> "HeadlessSession":
        if shutil.which("claude") is None:
            pytest.skip("claude CLI not on PATH")
        self._trace_file = open(self.trace_path, "w")
        # STORY_SIM_HEADLESS_TEST tells this repo's own Stop hooks (see
        # .claude/hooks/stop-docstring-check.sh) that this subprocess is an
        # automated responder, not an interactive session with a user who
        # could act on a nudge -- otherwise a hook's feedback derails the
        # turn into answering the nudge instead of the test's own
        # instruction, and the test sees that as an unrelated failure.
        #
        # IACS_DATABASE_URL points the sibling iacs-mcp server (also
        # allowed via _MCP_TOOL_ARGS) at this exact save's own Postgres
        # schema -- the same URL story-simulator's own registrar connects
        # to (see registry_url) -- computed here, before either MCP child
        # process spawns, since it can't be known until save_dir is
        # chosen. Without this, iacs-mcp would default to its own
        # unrelated example manifest, making its tools (list_component_types,
        # view_component, ...) useless against this save's actual state --
        # exactly the gap that let the model invent a nonexistent
        # component name instead of finding the real `location` schema.
        env = {**os.environ, "STORY_SIM_HEADLESS_TEST": "1", "IACS_DATABASE_URL": registry_url(self.save_dir)}
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
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        return self

    def send_turn(self, prompt: str) -> str:
        """Send one prompt on the ongoing conversation and block for its narrated reply.

        Every raw line read from the subprocess -- not just the final
        result -- is appended to `self.trace_path` as it arrives, so a
        failure (or a passing-but-suspicious run) can be inspected after
        the fact instead of only ever seeing the narrated text this method
        returns.
        """
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
                if self._trace_file is not None:
                    self._trace_file.write(line)
                    self._trace_file.flush()
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
        message = f"{message}\ntrace: {self.trace_path}\nstderr: {stderr}"
        self.close()
        pytest.fail(message)

    def close(self) -> None:
        if self._trace_file is not None:
            self._trace_file.close()
            self._trace_file = None
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
    current row per entity rather than assuming a single write. Filters via
    `aliases` (iacs's own alias-resolution, not a local re-filter) since
    `alias` here is always expected to name exactly one entity.
    """
    df = safe_view_current(registrar, "location.value", aliases=alias)
    if df is None or df.empty:
        return None
    return str(df.iloc[-1]["location.value"])


def _parked_at(location: str | None, spot: str) -> bool:
    """Loosely checks a recorded `location` value names `spot` (e.g.
    "parking_spot_1" or "street"), not any one exact phrasing.
    `location`'s own schema (manifest/builtins.yaml) calls it a "short
    freeform phrase", and confirmed live that a model's correct answer can
    reasonably come out phrased several ways ("parked in parking_spot_1"
    vs. just "parking_spot_1") -- the model shouldn't have to guess the
    one exact wording a test hardcodes."""
    return location is not None and spot in location


def _event_states(registrar: Registrar) -> dict[str, str]:
    """Map of {event_alias: current event_state.value}, or {} if nothing's been recorded yet."""
    df = safe_view_current(registrar, "event_state.value")
    if df is None:
        return {}
    return dict(zip(df["entity_id.alias"], df["event_state.value"]))


def _write_time(registrar: Registrar, component_type: str, alias: str) -> float | None:
    """The world time (see core._next_time_stamp) `component_type` was
    last written for `alias` -- the end_time of whichever event's own
    resolution turn made that write (every write made while resolving one
    event shares that event's own start_time + duration as "now"), or
    None if nothing's been recorded yet.

    Order evidence for live tests that no longer pace themselves one
    event per turn (see #61/docs/manifest/history.yaml): comparing these
    recorded world-times across entities confirms each one's outcome was
    produced while its own event resolved, not guessed independent of
    when that event's end_time was actually reached -- regardless of how
    many actual conversation turns the model took to get there.
    """
    df = registrar.view_df(component_type, aliases=alias)
    if df.empty:
        return None
    return float(df.iloc[-1][f"{component_type}.time"])


# Reused across live tests that no longer pace themselves one event per
# turn (see #61/docs/manifest/history.yaml: project_history.
# live_tests_decoupled_from_turn_count): let the model run the whole
# batch of events in as many or as few turns/tool-calls as it wants,
# rather than forcing it to stop after each one -- what these tests check
# is the final outcome and order, not how it got there.
_RUN_TO_DONE_INSTRUCTION = (
    "Call advance_simulation and keep answering its prompts (resolve, then plan, for "
    "whatever event it names, recording each decision via update_registry) until its "
    "status is \"done\". Don't narrate anything back to me."
)


@pytest.mark.live
def test_car_parking_core_sim(tmp_path):
    """Three cars must work out their own arrival order from raw facts, then
    correctly divide up a two-spot parking lot on a first-come-first-served basis.

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
    sort (soonest end_time first) pops them in the real arrival order (B, C,
    A), not start order or trip length. That's what makes each event's own
    resolution answerable with "very basic reasoning": by the time any one
    event resolves, whichever spots earlier events already claimed
    (recorded on the relevant car's own `location`) are genuinely already
    claimed, not a guess about entities that haven't been touched yet.

    Deliberately checks only the *final* result, not turn-by-turn state
    (see #61/docs/manifest/history.yaml: project_history.
    live_tests_decoupled_from_turn_count) -- the model runs the whole
    batch in one open-ended instruction, in as many or as few
    advance_simulation round-trips as it wants. What matters is (1) each
    car's final location and (2) that the *order* was actually respected,
    not the turn count. Order evidence comes from each car's `location`
    write being time-stamped with its own trip event's end_time (world
    time -- see core._next_time_stamp: every write made while resolving
    one event shares that event's own end_time as "now") -- confirming
    car_b's spot was recorded while resolving car_b_trip specifically,
    not retroactively or out of turn.
    """
    save_dir = tmp_path / "test_save"

    with HeadlessSession(save_dir) as session:
        print(f"HeadlessSession trace: {session.trace_path}")
        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={PARKING_SCENARIO_DIR} "
            f"to open a story-simulator world. Then {_RUN_TO_DONE_INSTRUCTION}"
        )
        r = _load_registrar(save_dir, narration)

        assert _parked_at(_location(r, "car_b"), "parking_spot_1"), (
            "Car B should be first to actually arrive (it left earlier than Car C by more "
            f"than their trip-length difference) and take the first spot -- narration: {narration!r}"
        )
        assert _parked_at(_location(r, "car_c"), "parking_spot_2"), (
            "Car C should be second to arrive (after Car B, before Car A) and take the "
            f"remaining dedicated spot -- narration: {narration!r}"
        )
        assert _parked_at(_location(r, "car_a"), "street"), (
            "Car A starts first but has the longest trip, so it should actually arrive last "
            f"and end up parked on the street -- narration: {narration!r}"
        )

        states = _event_states(r)
        assert states.get("car_b_trip") == "complete", states
        assert states.get("car_c_trip") == "complete", states
        assert states.get("car_a_trip") == "complete", states

        times = {alias: _write_time(r, "location", alias) for alias in ("car_b", "car_c", "car_a")}
        assert times["car_b"] == pytest.approx(1020), (
            f"car_b's location should be recorded at car_b_trip's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_c"] == pytest.approx(1080), (
            f"car_c's location should be recorded at car_c_trip's own end_time -- {times}, narration: {narration!r}"
        )
        assert times["car_a"] == pytest.approx(1800), (
            f"car_a's location should be recorded at car_a_trip's own end_time -- {times}, narration: {narration!r}"
        )
