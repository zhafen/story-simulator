from pathlib import Path

import pytest

import pandas as pd

from story_simulator.config import LIVING_WORLD_DIR
from story_simulator.interpreter import Interpreter
from story_simulator.systems import MapSystem
from story_simulator.world import EnsembleWorld, MirrorWorld


def test_startup_and_exit():

    p = Interpreter(MirrorWorld())
    assert p.input("Hello there.") == "Hello there."

    assert not p.stopped
    p.input("/quit")
    assert p.stopped


@pytest.mark.live
def test_startup_one_loop_save(tmp_path):
    """This test starts up an EnsembleWorld, and does a single
    loop, with the player character asking a simple question.
    This should trigger at least:
    1. The Resolver agent responding to the player.
    2. The Archivist transcribing entities described by the Resolver into iacs EC files, with the help of the iacs MCP.
    """

    # Setup
    save_dir = tmp_path / "test_save"
    w = EnsembleWorld(save_dir=save_dir)
    p = Interpreter(w)

    # Do the loop
    stdout = p.input("I look around. What do I see?")

    # The player should see mention of the empty expanse and the door.
    assert "door" in stdout.lower()
    assert "empty" in stdout.lower()

    # Load saved data using iacs
    # In the base scenario, there should be the following entities:
    # The player, with at least a position component and a player_character component
    # The door, with at least a position component
    r = w.registry
    # At least two positions
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
    # At least two appearance components
    assert r.get("appearance").count().execute() >= 2


@pytest.mark.live
def test_move(tmp_path):
    """This test checks that the player can use the interpreter to move, and which
    entities are active will be updated as they do so.

    Starting out there should be the player, a door, and a vast empty expanse,
    and that should be the only things the player can interact with.
    The player should be able to go to the door, walk out, and walk half a kilometer
    in the positive y-direction to find a desk with a journal on it.
    They should be able to see the desk, but no longer see the door.
    Then they should be able to turn around and walk back and see the door and expanse
    again, but not the desk anymore.

    Position assertions use ROUGHLY_THERE tolerance rather than an exact
    target: the Resolver/Archivist derive the player's position from
    freeform narration, so it lands close to the intended spot rather than
    exactly on it. The tolerance stays comfortably under MapSystem's default
    active radius (20m) so the active/inactive entity assertions, which are
    the real check that movement actually worked, stay meaningful regardless
    of the exact narrated distance.

    The journaling desk is only part of the living world's setting (not the
    plain default world), so this exercises the living world explicitly.
    """
    ROUGHLY_THERE = 15.0

    ###################################
    # TURN 0: Startup

    # Setup
    save_dir = tmp_path / "test_save"
    w = EnsembleWorld(save_dir=save_dir, settings_fp=LIVING_WORLD_DIR)
    p = Interpreter(w)
    r = w.registry

    # Check that the door and the vast expanse are active
    # and the journal, pen, and desk are not
    starting_objects = ["door", "expanse"]
    destination_objects = [
        "journaling_desk.journal",
        "journaling_desk.pen",
        "journaling_desk.desk",
    ]
    active = r.view("active").execute()
    assert pd.Series(starting_objects).isin(active["entity_id.alias"]).all()
    assert (~pd.Series(destination_objects).isin(active["entity_id.alias"])).all()

    # Check that the player starts exactly at the origin — this comes
    # straight from the seeded save data, not from any narration, so it's
    # deterministic and doesn't need tolerance.
    assert MapSystem.distance(w.registrar, "player", (0.0, 0.0)) < 1

    ###################################
    # TURN 1: Move to destination

    # Instruct to move
    stdout = p.input(
        "I go out the door and walk 500 meters straight forward. What do I see?"
    )

    # Check that the player arrives roughly at the intended location.
    assert MapSystem.distance(w.registrar, "player", (0.0, 500.0)) < ROUGHLY_THERE

    # The player should see the journaling desk, etc. — at least one by name
    # rather than requiring every one verbatim, since which specific items
    # the narration calls out by name (versus just describing the scene) is
    # itself a narrative choice, not a fact this test needs to pin down.
    assert any(obj.rsplit(".", maxsplit=1)[-1] in stdout.lower() for obj in destination_objects)

    # Check the inverse of the above
    # and the journal, pen, and desk are not
    active = r.view("active").execute()
    assert pd.Series(destination_objects).isin(active["entity_id.alias"]).all()
    assert (~pd.Series(starting_objects).isin(active["entity_id.alias"])).all()

    ###################################
    # TURN 2: Move back to origin

    # Go back toward the door, but stop beside it rather than going
    # *through* it: the living world's core mechanic is that walking
    # through the door always advances further (a new door, a year later,
    # another km south; see data/living_world/setting.yaml), so "go through
    # it" phrasing has the Resolver treat this as another forward teleport
    # instead of a return. Naming the door explicitly as where they stop
    # (rather than just "back where I started") also gives the Archivist a
    # concrete, already-positioned landmark to snap the player's new
    # position onto (per archivist.yaml's own "arriving at it, standing
    # next to it" rule) instead of having to compute it from a vaguer
    # description with nothing to anchor to.
    stdout = p.input(
        "I turn around and walk 500 meters back toward the door, stopping "
        "right beside it without going through it."
    )

    # Check that the player is back roughly where they started.
    assert MapSystem.distance(w.registrar, "player", (0.0, 0.0)) < ROUGHLY_THERE

    # The player should see the starting objects — at least one by name.
    assert any(obj.rsplit(".", maxsplit=1)[-1] in stdout.lower() for obj in starting_objects)

    # Check the starting objects are active again
    active = r.view("active").execute()
    assert pd.Series(starting_objects).isin(active["entity_id.alias"]).all()
    assert (~pd.Series(destination_objects).isin(active["entity_id.alias"])).all()


@pytest.mark.live
def test_npc(tmp_path):
    """NPCs use the exact same interface as players, but with the critical difference
    that the text sent to the interpreter is generated by an agent. The NPC
    owns "memory" components, each one linking it to an entity it has
    perceived; it can only access entities it has a memory of.

    Asserts the NPC is exploring under its own agenda ("go where I haven't
    explored yet") two ways: it has moved a nontrivial distance from where
    it started, and it has discovered at least one entity beyond the ones
    the world started with. Neither assertion pins an exact position or
    turn — a single decision might reasonably look around before actually
    moving, so several turns are given to act on its agenda rather than
    asserting on any one turn's outcome specifically.
    """

    settings_dir = Path("tests") / "data" / "settings" / "npc"

    # Setup
    save_dir = tmp_path / "test_save"
    w = EnsembleWorld(save_dir=save_dir, settings_fp=settings_dir)

    # Check that the NPC starts at the origin
    assert MapSystem.distance(w.registrar, "traveler", (0.0, 0.0)) < 1

    starting_aliases = set(
        w.registry.view_current(["position.x"]).execute()["entity_id.alias"]
    )

    # Advance the world several turns, giving the agenda-driven NPC room to
    # actually act on "go where I haven't explored" rather than requiring
    # it to move on the very first or second decision.
    for _ in range(4):
        w.advance()

    # The NPC should have moved a meaningful distance under its own agenda...
    assert MapSystem.distance(w.registrar, "traveler", (0.0, 0.0)) > 0.5

    # ...and discovered something new along the way.
    positions = w.registry.view_current(["position.x"]).execute()
    discovered_aliases = set(positions["entity_id.alias"]) - starting_aliases
    assert discovered_aliases
