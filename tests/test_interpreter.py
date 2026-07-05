from story_simulator.interpreter import Interpreter
from story_simulator.world import MirrorWorld


def test_defaults_to_mirror_world():
    interpreter = Interpreter()
    assert isinstance(interpreter.world, MirrorWorld)


def test_plain_text_returns_world_response():
    interpreter = Interpreter(world=MirrorWorld())
    assert interpreter.input("hello there") == "hello there"


def test_unknown_command_returns_none_and_does_not_stop():
    interpreter = Interpreter(world=MirrorWorld())
    assert interpreter.input("/help") is None
    assert interpreter.stopped is False


def test_quit_command_stops_and_returns_none():
    interpreter = Interpreter(world=MirrorWorld())
    assert interpreter.input("/quit") is None
    assert interpreter.stopped is True
