"""Pure-geometry tests for story_simulator.physics (no registry)."""

from story_simulator.physics import Body, collides, inside

CAR = Body("car", (0.0, 0.0, 0.0), 2.0, solid=True)


def test_overlapping_solids_collide():
    assert collides(CAR, Body("other", (3.0, 0.0, 0.0), 2.0, solid=True))


def test_touching_or_apart_solids_dont_collide():
    assert not collides(CAR, Body("other", (4.0, 0.0, 0.0), 2.0, solid=True))
    assert not collides(CAR, Body("other", (10.0, 0.0, 0.0), 2.0, solid=True))


def test_regions_never_collide():
    assert not collides(CAR, Body("spot", (0.0, 0.0, 0.0), 3.0, solid=False))


def test_inside_requires_whole_sphere_within_region():
    assert inside(CAR, Body("spot", (1.0, 0.0, 0.0), 3.0, solid=False))
    assert not inside(CAR, Body("spot", (1.5, 0.0, 0.0), 3.0, solid=False))


def test_nothing_is_inside_a_solid():
    assert not inside(CAR, Body("truck", (0.0, 0.0, 0.0), 5.0, solid=True))
