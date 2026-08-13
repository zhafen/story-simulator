"""Shared infrastructure for live end-to-end tests that drive story-simulator-mcp
through a real MCP client -- `HeadlessSession` and registry-reading helpers,
imported by tests/test_race_placement_live.py and
tests/test_parking_split_live.py. Carries no live test of its own: the
original combined driving+parking scenario this file used to test
(test_car_parking_core_sim) was removed once #57 established that
combined event resolves unreliably in a way the split-events structure
(tests/test_parking_split_live.py) doesn't -- see docs/manifest/
history.yaml: project_history.combined_parking_test_removed.

There is no in-process narrator to call directly (see
docs/manifest/history.yaml: project_history.turn_pipeline_removed), so
`HeadlessSession` spawns `claude -p` as a real subprocess against this
repo's .mcp.json, exactly the way the README's quick-start describes a
client connecting.

Written for the current event-entity simulation loop (no character/NPC
module -- see docs/architecture.md and CLAUDE.md's shelving note): world
state is `event` entities, each ready to resolve once world time reaches
its own end_time (start_time + duration), and every such event resolves via two separate
responder calls (resolve, then plan) at responder="host"
(`story_simulator.config.event_responder`'s default). The connected agent
is expected to decide each step itself, looking up whatever it needs via
view_registry/view_entity and recording its own decisions via
update_registry, exactly as the server's own tool instructions describe.

The character-module-era tests that used to live in this file (NPC/move
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
        # Accumulated across every send_turn call this session makes (a
        # session is usually several turns -- resolve/plan per event) --
        # each turn's "result" event already reports its own cost/usage
        # (see send_turn), this just sums them so a caller can read one
        # total for the whole session instead of re-deriving it from the
        # trace file after the fact. #75: needed to compare live-test
        # spend against the user's weekly usage allotment.
        self.total_cost_usd: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cache_read_tokens: int = 0
        self.total_cache_creation_tokens: int = 0
        self.total_duration_api_ms: int = 0

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
                    self._accumulate_usage(event)
                    return event["result"]
        finally:
            sel.close()

    def _accumulate_usage(self, result_event: dict) -> None:
        self.total_cost_usd += result_event.get("total_cost_usd", 0.0) or 0.0
        usage = result_event.get("usage") or {}
        self.total_input_tokens += usage.get("input_tokens", 0) or 0
        self.total_output_tokens += usage.get("output_tokens", 0) or 0
        self.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0) or 0
        self.total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0) or 0
        self.total_duration_api_ms += result_event.get("duration_api_ms", 0) or 0

    def usage_summary(self) -> dict:
        """This session's usage so far, summed across every send_turn call.

        `duration_api_ms` is time actually spent generating (the model's
        own "active" time), not this process's wall-clock time -- the
        metric that maps onto a usage-plan's hours-per-week allotment.
        """
        return {
            "total_cost_usd": self.total_cost_usd,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cache_read_input_tokens": self.total_cache_read_tokens,
            "cache_creation_input_tokens": self.total_cache_creation_tokens,
            "duration_api_ms": self.total_duration_api_ms,
        }

    def _fail(self, message: str) -> None:
        stderr = self.proc.stderr.read() if self.proc and self.proc.stderr else ""
        message = f"{message}\ntrace: {self.trace_path}\nstderr: {stderr}"
        self.close()
        pytest.fail(message)

    def close(self) -> None:
        if self._trace_file is not None:
            self._trace_file.close()
            self._trace_file = None
            # Persisted next to the trace unconditionally (not just when a
            # caller like location_write_harness.py bothers to read
            # usage_summary() itself) so every live test's spend is
            # recoverable after the fact, matching how the raw trace
            # itself is already kept regardless of whether a given test
            # happens to fail.
            usage_path = self.trace_path.with_suffix(".usage.json")
            usage_path.write_text(json.dumps(self.usage_summary(), indent=2))
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


# Intrinsic iacs bookkeeping component types every entity has a row in
# regardless of what anyone wrote -- entity_id (alias/filepath/hash) and
# component_type (which types this entity declares/uses). Not something
# a model ever chooses to write, so always excluded from
# _unexpected_components's result rather than making every caller repeat
# this same exclusion in its own `expected` set. Caught live: the first
# #83-instrumented run reported these on literally every rep, burying the
# one real misfire (`state`) in constant noise.
_ALWAYS_PRESENT_META_COMPONENTS = {"entity_id", "component_type"}


def _unexpected_components(registrar: Registrar, alias: str, expected: set[str]) -> set[str]:
    """Component types currently recorded on `alias` beyond `expected`
    (plus the always-present meta types, see
    _ALWAYS_PRESENT_META_COMPONENTS) -- #83: names *what* got written
    instead of the intended field when a check like
    `_parked_at(_location(...))` fails, rather than just noting that the
    intended field is empty. `expected` should cover both the scenario's
    starting components and whatever a fully correct write is supposed
    to add (e.g. {"object", "description", "location"} for
    tests/data/scenarios/location_write_isolated's car_a) -- any
    component type showing up outside that set is a plausible
    misattribution candidate (see #63's `parent`/`todo`/`parking_location`
    pattern), not proof of one: a legitimate future scenario could add
    components beyond `expected` for reasons unrelated to any bug.
    """
    return set(registrar.view_entity_df(alias)) - expected - _ALWAYS_PRESENT_META_COMPONENTS


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


