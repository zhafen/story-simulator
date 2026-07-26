from pathlib import Path

import pytest

import pandas as pd

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
    """
    ###################################
    # TURN 0: Startup

    # Setup
    save_dir = tmp_path / "test_save"
    w = EnsembleWorld(save_dir=save_dir)
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

    # Check that the player starts in the right place
    assert MapSystem.distance(w.registrar, "player", (0.0, 0.0)) < 1

    ###################################
    # TURN 1: Move to destination

    # Instruct to move
    stdout = p.input(
        "I go out the door and walk 500 meters straight forward. What do I see?"
    )

    # Check that the player arrives at the right location
    assert MapSystem.distance(w.registrar, "player", (0.0, 500.0)) < 1

    # The player should see the journaling desk, etc.
    for obj in destination_objects:
        assert obj.rsplit(".", maxsplit=1)[-1] in stdout.lower()

    # Check the inverse of the above
    # and the journal, pen, and desk are not
    active = r.view("active").execute()
    assert pd.Series(destination_objects).isin(active["entity_id.alias"]).all()
    assert (~pd.Series(starting_objects).isin(active["entity_id.alias"])).all()

    ###################################
    # TURN 2: Move back to origin

    # Go back to the door.
    stdout = p.input("I walk back to the door and go through it.")

    # Check that the player is back where expected
    assert MapSystem.distance(w.registrar, "player", (0.0, 0.0)) < 1

    # The player should see the starting objects
    for obj in starting_objects:
        assert obj.rsplit(".", maxsplit=1)[-1] in stdout.lower()

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
    """

    settings_dir = Path("tests") / "data" / "settings" / "npc"

    # Setup
    save_dir = tmp_path / "test_save"
    w = EnsembleWorld(save_dir=save_dir, settings_fp=settings_dir)

    # Check that the NPC starts at the origin
    assert MapSystem.distance(w.registrar, "traveler", (0.0, 0.0)) < 1

    # Advance the world two turns
    w.advance()
    w.advance()

    # Check that the NPC is no longer within 1 meter of the origin
    assert MapSystem.distance(w.registrar, "traveler", (0.0, 0.0)) > 1
