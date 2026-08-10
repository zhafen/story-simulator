import pytest

from story_simulator.collision import resolve_collision


def test_elastic_equal_mass_collision_swaps_velocities():
    """e=1, equal masses: a textbook check -- the two velocities trade places."""
    result = resolve_collision(1.0, (3.0, 0.0, 0.0), 1.0, (-1.0, 0.0, 0.0), restitution=1.0)

    assert result.velocity_a_after == pytest.approx((-1.0, 0.0, 0.0))
    assert result.velocity_b_after == pytest.approx((3.0, 0.0, 0.0))


def test_elastic_collision_conserves_kinetic_energy():
    result = resolve_collision(2.0, (3.0, 1.0, 0.0), 5.0, (-2.0, 0.0, 4.0), restitution=1.0)

    assert result.kinetic_energy_after == pytest.approx(result.kinetic_energy_before)
    assert result.energy_lost == pytest.approx(0.0)


def test_perfectly_inelastic_collision_yields_equal_final_velocities():
    """e=0: both objects end up moving together at the momentum-conserving common velocity."""
    result = resolve_collision(1.0, (3.0, 0.0, 0.0), 1.0, (-1.0, 0.0, 0.0), restitution=0.0)

    assert result.velocity_a_after == pytest.approx(result.velocity_b_after)
    assert result.velocity_a_after == pytest.approx((1.0, 0.0, 0.0))


def test_collision_conserves_momentum_for_partial_restitution():
    mass_a, mass_b = 2.0, 3.0
    velocity_a, velocity_b = (3.0, 0.0, 0.0), (-2.0, 0.0, 0.0)

    result = resolve_collision(mass_a, velocity_a, mass_b, velocity_b, restitution=0.5)

    def momentum(mass, velocity):
        return tuple(mass * component for component in velocity)

    before = tuple(
        a + b for a, b in zip(momentum(mass_a, velocity_a), momentum(mass_b, velocity_b))
    )
    after = tuple(
        a + b
        for a, b in zip(
            momentum(mass_a, result.velocity_a_after), momentum(mass_b, result.velocity_b_after)
        )
    )
    assert after == pytest.approx(before)


def test_partial_restitution_matches_hand_computed_outcome():
    """m_a=2, v_a=3; m_b=3, v_b=-2; e=0.5 -- worked out by hand in the collision-math design."""
    result = resolve_collision(2.0, (3.0, 0.0, 0.0), 3.0, (-2.0, 0.0, 0.0), restitution=0.5)

    assert result.velocity_a_after == pytest.approx((-1.5, 0.0, 0.0))
    assert result.velocity_b_after == pytest.approx((1.0, 0.0, 0.0))
    assert result.kinetic_energy_before == pytest.approx(15.0)
    assert result.kinetic_energy_after == pytest.approx(3.75)
    assert result.energy_lost == pytest.approx(11.25)
