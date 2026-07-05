import pytest

from story_simulator.world import World, MirrorWorld


def test_base_world_cannot_be_instantiated():
    with pytest.raises(TypeError):
        World()


def test_mirror_world_echoes_text():
    world = MirrorWorld()
    assert world.respond("hello there") == "hello there"
