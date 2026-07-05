from story_simulator.repl import handle_input, is_quit
from story_simulator.world import MirrorWorld


def test_is_quit_matches_quit_command():
    assert is_quit("/quit") is True
    assert is_quit("  /quit  ") is True


def test_is_quit_does_not_match_other_text():
    assert is_quit("hello there") is False
    assert is_quit("/help") is False


def test_handle_input_returns_world_response_for_plain_text():
    world = MirrorWorld()
    assert handle_input(world, "hello there") == "hello there"


def test_handle_input_returns_none_for_a_command():
    world = MirrorWorld()
    assert handle_input(world, "/help") is None
