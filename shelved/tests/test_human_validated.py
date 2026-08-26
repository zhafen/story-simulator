"""Live end-to-end tests that drive story-simulator-mcp through a real MCP client.

There is no in-process narrator to call directly, so
these spawn `claude -p` as a real subprocess against this repo's .mcp.json,
exactly the way the README's quick-start describes a client connecting.
Deliberately not built on story_simulator.agents.run_tool_loop --
reusing this project's own narrowly-scoped agent-loop code (built for
advance_npc_turn's decide/narrate step, not general narration) as the test
driver would mean the "client" checking the server was written by the same
hand, with the same assumptions, as the server itself.

Anything needing more than one turn (test_move, test_npc) uses HeadlessSession
to drive one continuous `claude -p` process over stream-json, rather than
chaining separate --resume calls. That's not just an optimization: the whole
point of using Postgres (over an embedded database like DuckDB) is that a
still-open session's connection doesn't block anyone else from reading --
a --resume chain would sidestep ever needing that, since each call is its own
process that fully exits (closing its connection) before the next one starts.
HeadlessSession keeps one story-simulator-mcp child alive for the test's
whole duration, so assertions between turns run against a schema that
process is still holding open, which is the actual property under test. It
also means start_world only needs calling once -- the registrar it opens
lives in that one process's memory for every later tool call in the same
session, unlike a fresh process per turn.
"""

import json
import selectors
import shutil
import subprocess
import time
from pathlib import Path

import ibis
import pandas as pd
import pytest

from emc2p.registrar import Registrar
from story_simulator.config import registry_schema_name, registry_url, resolve_database_dsn
from story_simulator.spatial import distance

REPO_ROOT = Path(__file__).parent.parent
NPC_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "npc"
MOVE_SCENARIO_DIR = REPO_ROOT / "tests" / "data" / "scenarios" / "move"

# Cheapest available model. Kept deliberately weak rather than swapped for a
# stronger one: story-simulator's tools need to hold up under a bad model's
# mistakes, not just a good one's, so that's the model these tests exercise.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"

# Bash/Task are explicitly denied everywhere below, not just left off the
# allowlist: a weak model, given the choice, sometimes reaches for "write a
# Python script that calls these functions directly" instead of just calling
# the MCP tools it already has, and an
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

    One prompt in, one narrated reply out, then the process exits -- for a
    test that only ever needs one turn, there's no session to keep alive.
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


class HeadlessSession:
    """One continuously-running `claude -p` process, driven over stream-json.

    Unlike separate --resume calls, this keeps a single story-simulator-mcp
    child process (and its Postgres connection) alive for the whole `with`
    block, so `send_turn`'s caller can read the registry in between turns
    while that process is still holding it open -- genuinely exercising the
    concurrent-access property the Postgres migration exists for, not just
    reading after everything has already exited.
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
    mistyped out of the prompt's text -- so this checks the schema was
    actually created for the exact `save_dir` the test used before
    reading it, rather than either silently reading
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


@pytest.mark.live
def test_startup_one_loop_save(tmp_path):
    """Starts a default-world save via story-simulator-mcp and looks around, in one turn.

    This should trigger at least:
    1. `start_world` seeding the save from the default world.
    2. The connected agent narrating back mention of the door and the empty expanse.
    """
    save_dir = tmp_path / "test_save"

    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} to open a story-simulator world. "
        "Then, as the player: I look around. What do I see?"
    )

    # The player should see mention of the empty expanse and the door.
    assert "door" in narration.lower()
    assert "empty" in narration.lower()

    # The claude -p subprocess (and the story-simulator-mcp server it spawned
    # as its own child) has exited by now, releasing its connection --
    # reconnect to the same schema to check what actually got recorded, the
    # same way the pre-MCP test read `w.registry` in-process.
    r = _load_registrar(save_dir, narration)

    # At least two positions (player, door; the default world's expanse too)
    assert r.get("position").count().execute() >= 2
    # One origin
    assert r.get("origin").count().execute() == 1
    # One character, of interaction type player
    assert (characters := r.get("character")).count().execute() == 1
    assert (
        characters.filter(characters.interaction_type == "player").count().execute()
        == 1
    )
    # At least one object, which is a door
    assert (objects := r.get("object")).count().execute() >= 1
    assert objects.filter(objects.type.contains("door")).count().execute() == 1
    # At least two of the default world's starting entities carry their own
    # description. (The old test checked an `appearance` component type;
    # that's since been retired in favor of iacs's own builtin `description`
    # -- which every declared component/field also uses for its own
    # docstring, so this filters down to the starting aliases rather than
    # counting the several dozen unrelated schema-doc rows that come with
    # any manifest.)
    descriptions = r.view("description").execute()
    starting_aliases = {"player", "door", "expanse"}
    assert descriptions["entity_id.alias"].isin(starting_aliases).sum() >= 2


@pytest.mark.live
def test_move(tmp_path):
    """Checks that the player can move, and which entities are `active` updates as they do.

    Starting out there should be the player, a door, and a vast empty expanse,
    and that should be the only things the player can interact with.
    The player should be able to go to the door, walk out, and walk half a kilometer
    in the positive y-direction to find a desk with a journal on it.
    They should be able to see the desk, but no longer see the door.
    Then they should be able to turn around and walk back and see the door and expanse
    again, but not the desk anymore.

    Position assertions use ROUGHLY_THERE tolerance rather than an exact
    target: the connected agent derives the player's position from freeform
    narration, so it lands close to the intended spot rather than exactly on
    it. The tolerance stays comfortably under `perceive`'s default radius
    (20m) so the active/inactive entity assertions, which are the real check
    that movement actually worked, stay meaningful regardless of the exact
    narrated distance.

    Uses a dedicated fixture (tests/data/scenarios/move), not the living
    world: the living world's core mechanic is that walking *through* the
    door always teleports the player further away (a new door, a year
    later, another km south; see data/living_world/scenario.yaml), which has
    nothing to do with what this test checks and only adds an ambiguity
    risk -- a weak model reading "go out the door" has been observed
    triggering the teleport instead of an ordinary move. The dedicated
    fixture carries the same player/door/expanse/journaling-desk layout
    with that mechanic simply absent, so there's nothing to accidentally
    trigger and the movement prompts don't need to route around it.

    Three turns on one continuous HeadlessSession: a baseline look (to
    establish the active-set contrast the rest of the test depends on), the
    move out, and the move back. Fewer wouldn't work -- the whole point is
    checking that active flips across a movement round-trip, which needs a
    real before/after on both ends. start_world is only called on the first
    turn -- the session's one story-simulator-mcp process keeps the same
    registrar in memory for every later turn, unlike separate --resume
    calls where each is a fresh process needing its own reconnect.
    """
    ROUGHLY_THERE = 15.0
    save_dir = tmp_path / "test_save"

    starting_objects = ["door", "expanse"]
    destination_objects = [
        "journaling_desk.journal",
        "journaling_desk.pen",
        "journaling_desk.desk",
    ]

    with HeadlessSession() as session:
        ###################################
        # TURN 0: Startup + baseline look

        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={MOVE_SCENARIO_DIR} "
            "to open a story-simulator world. Then, as the player: I look around. What do I see?"
        )

        # Read while the session's story-simulator-mcp process is still
        # alive and holding its own connection open, not after it exits.
        r = _load_registrar(save_dir, narration)
        # Check that the door and the vast expanse are active, and the
        # journal, pen, and desk are not.
        active = r.view("active").execute()
        assert pd.Series(starting_objects).isin(active["entity_id.alias"]).all()
        assert (~pd.Series(destination_objects).isin(active["entity_id.alias"])).all()
        # Check that the player starts exactly at the origin -- this comes
        # straight from the seeded save data, not from any narration, so
        # it's deterministic and doesn't need tolerance.
        assert distance(r, "player", (0.0, 0.0)) < 1

        ###################################
        # TURN 1: Move to destination

        narration = session.send_turn(
            "As the player: I walk past the door, out into the empty expanse, and "
            "continue 500 meters straight forward. What do I see? Remember to record "
            "the new position with update_registry, not just narrate it."
        )

        r = _load_registrar(save_dir, narration)
        assert distance(r, "player", (0.0, 500.0)) < ROUGHLY_THERE, (
            f"player position never updated -- narration: {narration!r}"
        )
        # The player should see the journaling desk, etc. -- at least one by
        # name rather than requiring every one verbatim, since which
        # specific items the narration calls out by name (versus just
        # describing the scene) is itself a narrative choice, not a fact
        # this test needs to pin down.
        assert any(
            obj.rsplit(".", maxsplit=1)[-1] in narration.lower() for obj in destination_objects
        )
        active = r.view("active").execute()
        assert pd.Series(destination_objects).isin(active["entity_id.alias"]).all()
        assert (~pd.Series(starting_objects).isin(active["entity_id.alias"])).all()

        ###################################
        # TURN 2: Move back to origin

        # Naming the door explicitly as where they stop (rather than just
        # "back where I started") gives the connected agent a concrete,
        # already-positioned landmark to snap the player's new position
        # onto, per the server's own system prompt.
        narration = session.send_turn(
            "As the player: I turn around and walk 500 meters back toward the door, "
            "stopping right beside it. Remember to record the new position with "
            "update_registry, not just narrate it."
        )

        r = _load_registrar(save_dir, narration)
        assert distance(r, "player", (0.0, 0.0)) < ROUGHLY_THERE, (
            f"player position never updated -- narration: {narration!r}"
        )
        assert any(obj.rsplit(".", maxsplit=1)[-1] in narration.lower() for obj in starting_objects)
        active = r.view("active").execute()
        assert pd.Series(starting_objects).isin(active["entity_id.alias"]).all()
        assert (~pd.Series(destination_objects).isin(active["entity_id.alias"])).all()


@pytest.mark.live
def test_npc(tmp_path):
    """NPCs use the exact same interface as players, but decided and narrated by advance_npc_turn.

    Asserts the NPC is exploring under its own agenda ("go where I haven't
    explored yet") two ways: it has moved a nontrivial distance from where
    it started, and it has discovered at least one entity beyond the ones
    the world started with. Neither assertion pins an exact position or
    turn -- a single decision might reasonably look around before actually
    moving, so advance_npc_turn is called several times to give it room to
    act on its agenda rather than asserting on any one call's outcome
    specifically.

    Two turns on one continuous HeadlessSession: a bare startup (no
    narration, no perceiving -- establishes the pre-advance baseline this
    test compares against), then a second turn that calls advance_npc_turn
    on its own four times in a row. Nobody needs to narrate an NPC's turn
    for it -- that's the whole point of the tool -- so unlike test_move
    this doesn't need a narrated turn per advance. Same one-process,
    call-start_world-once session as test_move, for the same reason: a
    fresh process per turn (via --resume) would have no registrar of its
    own and would need start_world called again on every turn, plus it
    would never actually exercise reading the registry while a session's
    connection is still open.
    """
    save_dir = tmp_path / "test_save"

    with HeadlessSession() as session:
        ###################################
        # TURN 0: Startup only -- establishes the pre-advance baseline

        narration = session.send_turn(
            f"Use start_world with save_dir={save_dir} and scenario_dir={NPC_SCENARIO_DIR} "
            "to open a story-simulator world. Don't call any other tools yet."
        )

        r = _load_registrar(save_dir, narration)
        # Check that the NPC starts at the origin.
        assert distance(r, "traveler", (0.0, 0.0)) < 1
        starting_aliases = set(r.view_current(["position.x"]).execute()["entity_id.alias"])

        ###################################
        # TURN 1: Advance the NPC several times, autonomously

        narration = session.send_turn(
            "Call the advance_npc_turn tool with npc_alias='traveler' four separate times, "
            "one after another. Don't narrate or decide anything yourself -- advance_npc_turn "
            "handles the whole turn on its own each time."
        )

        r = _load_registrar(save_dir, narration)
        # The NPC should have moved a meaningful distance under its own agenda...
        assert distance(r, "traveler", (0.0, 0.0)) > 0.5
        # ...and discovered something new along the way.
        positions = r.view_current(["position.x"]).execute()
        discovered_aliases = set(positions["entity_id.alias"]) - starting_aliases
        assert discovered_aliases
