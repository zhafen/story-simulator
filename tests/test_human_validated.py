from pathlib import Path

from story_simulator.interpreter import Interpreter
from story_simulator.world import EnsembleWorld, MirrorWorld

DATA_DIR = Path(__file__).parent / "data"


def test_startup_and_exit():

    p = Interpreter(MirrorWorld())
    assert p.input("Hello there.") == "Hello there."

    assert not p.stopped
    p.input("/quit")
    assert p.stopped

def test_startup_one_loop_save():
    """This test starts up an EnsembleWorld, and does a single
    loop, with the player character asking a simple question.
    This should trigger at least:
    1. The WorldSoul agent responding to the player.
    2. The Archivist transcribing entities described by the WorldSoul into iacs EC files, with the help of the iacs MCP.
    """

    # Setup
    save_dir = DATA_DIR / "test_save"
    w = EnsembleWorld(save_dir=save_dir)
    p = Interpreter(w)

    # Do the loop
    p.input("I look around. What do I see?")

    # Load saved data using iacs
    # In the base scenario, there should be the following entities:
    # The player, with at least a position component and a player_character component
    # The door, with at least a position component
    a = w.architect
    # At least two positions
    assert a.get("position").count().execute() >= 2
    # One origin
    assert a.get("origin").count().execute() == 1
    # One character, of interaction type player
    assert (characters := a.get("character")).count().execute() == 1
    assert characters.filter(characters.interaction_type == "player").count().execute() == 1
    # At least one object, which is a door
    assert (objects := a.get("object")).count().execute() >= 1
    assert objects.filter(objects.type.contains("door")).count().execute() == 1
    # At least two appearance components
    assert a.get("appearance").count().execute() >= 2
