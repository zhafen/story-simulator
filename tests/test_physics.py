"""Pure-geometry tests for story_simulator.physics (no registry)."""

from story_simulator.physics import Body, collides, inside

CAR = Body("car", (0.0, 0.0, 0.0), (4.5, 2.0, 1.5), solid=True)


def _car(x: float, y: float, z: float = 0.0) -> Body:
    """Another car-sized solid at (x, y, z)."""
    return Body("other", (x, y, z), (4.5, 2.0, 1.5), solid=True)


def test_overlapping_solids_collide():
    """Overlapping solids collide."""
    assert collides(CAR, _car(4.0, 0.0))  # nose to tail, overlapping 0.5 m


def test_forward_axis_is_x():
    # 3 m apart: overlapping along x (length 4.5), clear along y (width 2).
    """Forward axis is x."""
    assert collides(CAR, _car(3.0, 0.0))
    assert not collides(CAR, _car(0.0, 3.0))


def test_touching_or_apart_solids_dont_collide():
    """Touching or apart solids dont collide."""
    assert not collides(CAR, _car(4.5, 0.0))
    assert not collides(CAR, _car(0.0, 0.0, 1.5))  # stacked: z spans position.z upward


def test_regions_never_collide():
    """Regions never collide."""
    assert not collides(CAR, Body("spot", (0.0, 0.0, 0.0), (5.5, 3.0, 3.0), solid=False))


def test_inside_requires_whole_box_within_region():
    """Inside requires whole box within region."""
    assert inside(CAR, Body("spot", (0.5, 0.0, 0.0), (5.5, 3.0, 3.0), solid=False))
    assert not inside(CAR, Body("spot", (1.0, 0.0, 0.0), (5.5, 3.0, 3.0), solid=False))
    assert not inside(CAR, Body("spot", (0.0, 0.0, 0.0), (5.5, 3.0, 1.0), solid=False))


def test_nothing_is_inside_a_solid():
    """Nothing is inside a solid."""
    assert not inside(CAR, Body("truck", (0.0, 0.0, 0.0), (10.0, 5.0, 5.0), solid=True))
