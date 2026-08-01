"""Live end-to-end tests that drive story-simulator-mcp through a real MCP client.

Post-MCP-rebuild replacement for the old tests (removed in acb2956 along with
EnsembleWorld/Interpreter): there is no in-process narrator left to call
directly, so these spawn `claude -p` as a real subprocess against this repo's
.mcp.json, exactly the way the README's quick-start describes a client
connecting. Deliberately not built on story_simulator.agents.run_tool_loop --
reusing this project's own narrowly-scoped agent-loop code (built for
advance_npc_turn's decide/narrate step, not general narration) as the test
driver would mean the "client" checking the server was written by the same
hand, with the same assumptions, as the server itself.

Anything needing more than one turn (test_move, test_npc) chains separate
`claude -p` calls with `--session-id`/`--resume` rather than one long-lived
process: each call fully exits before the next starts, which is also what
lets the registry be read freely in the gaps -- no special concurrency
handling needed, unlike peeking mid-turn.
"""

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import ibis
import pandas as pd
import pytest

from iacs.registrar import Registrar
from story_simulator.config import (
    LIVING_WORLD_DIR,
    registry_schema_name,
    registry_url,
    resolve_database_dsn,
)
from story_simulator.spatial import distance

REPO_ROOT = Path(__file__).parent.parent
NPC_SETTINGS_DIR = REPO_ROOT / "tests" / "data" / "settings" / "npc"

# Cheapest available model. Kept deliberately weak rather than swapped for a
# stronger one: story-simulator's tools need to hold up under a bad model's
# mistakes, not just a good one's, so that's the model these tests exercise.
LOW_QUALITY_MODEL = "claude-haiku-4-5-20251001"


def _run_headless_turn(
    prompt: str,
    *,
    model: str = LOW_QUALITY_MODEL,
    timeout: int = 180,
    session_id: str | None = None,
    resume: bool = False,
) -> str:
    """Run one headless `claude -p` turn against this repo's MCP servers.

    One prompt in, one narrated reply out -- whatever tool calls
    story-simulator-mcp needs to answer it happen inside that single turn,
    same as a real player's message would trigger. Pass `session_id` (and
    `resume=True` on every call after the first) to chain several of these
    into one ongoing conversation instead of independent one-shot turns.

    Bash/Task are explicitly denied, not just left off the allowlist: a weak
    model, given the choice, sometimes reaches for "write a Python script
    that calls these functions directly" instead of just calling the MCP
    tools it already has -- confirmed happening in practice -- and an
    unapproved Bash call in headless mode doesn't fail fast, it sits
    waiting for an approval that never comes. Denying it outright removes
    the option instead of hoping the model doesn't reach for it.
    """
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not on PATH")

    session_args = []
    if session_id is not None:
        session_args = ["--resume" if resume else "--session-id", session_id]

    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--mcp-config",
            ".mcp.json",
            "--strict-mcp-config",
            "--allowedTools",
            "mcp__story-simulator__*",
            "mcp__story_simulator__*",
            "mcp__iacs__*",
            "--disallowedTools",
            "Bash",
            "Task",
            "--model",
            model,
            "--output-format",
            "json",
            *session_args,
        ],
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
    but the call itself doesn't hardcode that. Every resumed turn spawns a
    fresh story-simulator-mcp process with no registrar of its own, so this
    is worth checking again after each one, not just the first.
    """
    schema = registry_schema_name(save_dir)
    base_con = ibis.connect(resolve_database_dsn())
    assert schema in base_con.list_databases(), (
        f"No registry schema exists for {save_dir} -- start_world was not "
        f"actually (re)called for this exact save_dir despite this "
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
    # same way the pre-MCP test read `w.registry` in-process. The registry
    # database lets any process open its own connection to shared, live
    # state, so this would work even before the subprocess exits.
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

    The journaling desk is only part of the living world's setting (not the
    plain default world), so this exercises the living world explicitly.

    Three turns, chained with --session-id/--resume: a baseline look (to
    establish the active-set contrast the rest of the test depends on), the
    move out, and the move back. Fewer wouldn't work -- the whole point is
    checking that active flips across a movement round-trip, which needs a
    real before/after on both ends.

    KNOWN GAP (reproduced 3/3 runs while writing this test, not prompt
    flakiness): the movement turn's same_as-targeted write sometimes forks a
    new entity (observed as both "world:player" and a fabricated
    "player_at_500") instead of resolving to the file-seeded "player"
    entity, which then makes get_entity_id's substring resolution for
    "player" ambiguous and raises ValueError deep in
    story_simulator.spatial._resolve_point instead of failing this test's
    own assertion cleanly. Root cause looks structural: start_world seeds
    entities via their literal YAML file path as source key, while every
    live write (perceive, update_registry) uses the shared WORLD_FILE_ID
    ("world") source key instead -- config.WORLD_FILE_ID's own docstring
    already warns merging under a different source key than an entity was
    created with forks a duplicate rather than updating the original. Not
    something this test's prompt wording can route around; flagged here
    rather than silently retried away.
    """
    ROUGHLY_THERE = 15.0
    save_dir = tmp_path / "test_save"
    session_id = str(uuid.uuid4())

    starting_objects = ["door", "expanse"]
    destination_objects = [
        "journaling_desk.journal",
        "journaling_desk.pen",
        "journaling_desk.desk",
    ]

    ###################################
    # TURN 0: Startup + baseline look

    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} and settings_dir={LIVING_WORLD_DIR} "
        "to open a story-simulator world. Then, as the player: I look around. What do I see?",
        session_id=session_id,
    )

    r = _load_registrar(save_dir, narration)
    # Check that the door and the vast expanse are active, and the journal,
    # pen, and desk are not.
    active = r.view("active").execute()
    assert pd.Series(starting_objects).isin(active["entity_id.alias"]).all()
    assert (~pd.Series(destination_objects).isin(active["entity_id.alias"])).all()
    # Check that the player starts exactly at the origin -- this comes
    # straight from the seeded save data, not from any narration, so it's
    # deterministic and doesn't need tolerance.
    assert distance(r, "player", (0.0, 0.0)) < 1

    ###################################
    # TURN 1: Move to destination

    # Every resumed turn is a brand-new story-simulator-mcp process with no
    # registrar of its own -- re-opening the same save_dir is a cheap no-op
    # (start_world doesn't reseed once a save has data), but it does need
    # asking for explicitly each time, rather than assuming the model will
    # infer it needs to reconnect on its own.
    #
    # Phrased to avoid the door itself: the living world's core mechanic is
    # that walking *through* the door always teleports further (a new door,
    # a year later, another km south; see data/living_world/setting.yaml),
    # so "go out the door" is ambiguous enough that a weak model reads it as
    # walking through it -- confirmed this happens in practice. Walking past
    # it into the expanse sidesteps the mechanic instead of relying on the
    # model to infer the distinction.
    #
    # The explicit "update the player's own position" reminder is likewise
    # earned, not decorative: a weak model, despite the server's own system
    # prompt already saying to reuse aliases via same_as, has been observed
    # inventing a brand-new entity (e.g. "player_at_500") for the new
    # location instead of updating "player" in place -- which then breaks
    # get_entity_id's substring resolution for "player" itself, since
    # "player_at_500" contains it as a prefix.
    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} again to reconnect to the world "
        "(it already has data, so this just reopens it). Then, as the player: I walk "
        "past the door, out into the empty expanse, and continue 500 meters straight "
        "forward -- I do not go through the door. Update the player's own existing "
        "position (same_as: player) rather than creating a new entity for the new "
        "location. What do I see?",
        session_id=session_id,
        resume=True,
        timeout=240,
    )

    r = _load_registrar(save_dir, narration)
    assert distance(r, "player", (0.0, 500.0)) < ROUGHLY_THERE
    # The player should see the journaling desk, etc. -- at least one by name
    # rather than requiring every one verbatim, since which specific items
    # the narration calls out by name (versus just describing the scene) is
    # itself a narrative choice, not a fact this test needs to pin down.
    assert any(
        obj.rsplit(".", maxsplit=1)[-1] in narration.lower() for obj in destination_objects
    )
    active = r.view("active").execute()
    assert pd.Series(destination_objects).isin(active["entity_id.alias"]).all()
    assert (~pd.Series(starting_objects).isin(active["entity_id.alias"])).all()

    ###################################
    # TURN 2: Move back to origin

    # Go back toward the door, but stop beside it rather than going *through*
    # it: the living world's core mechanic is that walking through the door
    # always advances further (a new door, a year later, another km south;
    # see data/living_world/setting.yaml), so "go through it" phrasing would
    # have the connected agent treat this as another forward teleport
    # instead of a return. Naming the door explicitly as where they stop
    # (rather than just "back where I started") also gives it a concrete,
    # already-positioned landmark to snap the player's new position onto.
    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} again to reconnect to the world. "
        "Then, as the player: I turn around and walk 500 meters back toward the door, "
        "stopping right beside it without going through it. Update the player's own "
        "existing position (same_as: player) rather than creating a new entity for the "
        "new location.",
        session_id=session_id,
        resume=True,
        timeout=240,
    )

    r = _load_registrar(save_dir, narration)
    assert distance(r, "player", (0.0, 0.0)) < ROUGHLY_THERE
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

    Two turns, chained: a bare startup (no narration, no perceiving --
    establishes the pre-advance baseline this test compares against), then
    a second turn that calls advance_npc_turn on its own four times in a
    row. Nobody needs to narrate an NPC's turn for it -- that's the whole
    point of the tool -- so unlike test_move this doesn't need a
    narrated turn per advance.
    """
    save_dir = tmp_path / "test_save"
    session_id = str(uuid.uuid4())

    ###################################
    # TURN 0: Startup only -- establishes the pre-advance baseline

    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} and settings_dir={NPC_SETTINGS_DIR} "
        "to open a story-simulator world. Don't call any other tools yet.",
        session_id=session_id,
    )

    r = _load_registrar(save_dir, narration)
    # Check that the NPC starts at the origin.
    assert distance(r, "traveler", (0.0, 0.0)) < 1
    starting_aliases = set(r.view_current(["position.x"]).execute()["entity_id.alias"])

    ###################################
    # TURN 1: Advance the NPC several times, autonomously

    # Every resumed turn is a brand-new story-simulator-mcp process with no
    # registrar of its own -- reconnecting needs asking for explicitly, same
    # as test_move (start_world doesn't reseed once a save has data).
    narration = _run_headless_turn(
        f"Use start_world with save_dir={save_dir} again to reconnect to the world "
        "(it already has data, so this just reopens it). Then call the advance_npc_turn "
        "tool with npc_alias='traveler' four separate times, one after another. Don't "
        "narrate or decide anything yourself -- advance_npc_turn handles the whole turn "
        "on its own each time.",
        session_id=session_id,
        resume=True,
        timeout=240,
    )

    r = _load_registrar(save_dir, narration)
    # The NPC should have moved a meaningful distance under its own agenda...
    assert distance(r, "traveler", (0.0, 0.0)) > 0.5
    # ...and discovered something new along the way.
    positions = r.view_current(["position.x"]).execute()
    discovered_aliases = set(positions["entity_id.alias"]) - starting_aliases
    assert discovered_aliases
