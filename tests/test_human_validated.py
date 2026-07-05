from story_simulator.interpreter import Interpreter


def test_startup_and_exit():

    p = Interpreter()
    assert p.input("Hello there.") == "Hello there."

    assert not p.stopped
    p.input("/quit")
    assert p.stopped
