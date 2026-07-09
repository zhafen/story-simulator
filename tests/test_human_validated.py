from story_simulator.interpreter import Interpreter
from story_simulator.world import EnsembleWorld, MirrorWorld


def test_startup_and_exit():

    p = Interpreter(MirrorWorld())
    assert p.input("Hello there.") == "Hello there."

    assert not p.stopped
    p.input("/quit")
    assert p.stopped

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
    p.input("I look around. What do I see?")

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
    assert characters.filter(characters.interaction_type == "player").count().execute() == 1
    # At least one object, which is a door
    assert (objects := r.get("object")).count().execute() >= 1
    assert objects.filter(objects.type.contains("door")).count().execute() == 1
    # At least two appearance components
    assert r.get("appearance").count().execute() >= 2
