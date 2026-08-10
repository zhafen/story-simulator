"""Pure two-body collision math: mass/velocity/restitution in, exact energy and momentum out.

`story_simulator.interaction.resolve_interaction` calls `resolve_collision`
once per surviving pair, after the Physics Resolver has estimated each
entity's velocity vector -- this module only does the arithmetic a narrator
shouldn't be trusted to get exactly right, the same reasoning
`story_simulator/spatial.py`'s plain distance/position math already follows.
No LLM calls, no registry access.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def kinetic_energy(mass: float, velocity: np.ndarray) -> float:
    """0.5 * mass * |velocity|^2 -- exposed for callers that need one object's KE after a collision."""
    return 0.5 * mass * float(np.dot(velocity, velocity))


@dataclass(frozen=True)
class CollisionResult:
    """The outcome of one two-body collision -- see `resolve_collision`."""

    velocity_a_after: np.ndarray
    velocity_b_after: np.ndarray
    kinetic_energy_before: float
    kinetic_energy_after: float

    @property
    def energy_lost(self) -> float:
        """Kinetic energy the collision dissipated (>= 0 for 0 <= restitution <= 1)."""
        return self.kinetic_energy_before - self.kinetic_energy_after


def resolve_collision(
    mass_a: float,
    velocity_a: np.ndarray,
    mass_b: float,
    velocity_b: np.ndarray,
    restitution: float,
) -> CollisionResult:
    """Work out both objects' post-collision velocities and the kinetic energy lost.

    Uses the standard vector form of the 1D restitution collision --
    momentum-conserving for any `restitution`, with `restitution` (1.0 =
    perfectly elastic, 0.0 = perfectly inelastic) setting how much of the
    closing velocity along the line of impact survives as separating
    velocity afterward:

        v_a' = v_a - (1 + e) * m_b / (m_a + m_b) * (v_a - v_b)
        v_b' = v_b + (1 + e) * m_a / (m_a + m_b) * (v_a - v_b)

    Frame-covariant (doesn't require `velocity_a`/`velocity_b` to already be
    in the center-of-mass frame, though that's what the Physics Resolver is
    asked to estimate), and needs no explicit contact normal since a
    narrative-scale resolver treats every impact as head-on rather than
    modeling glancing blows or rotation.
    """
    velocity_a = np.asarray(velocity_a, dtype=float)
    velocity_b = np.asarray(velocity_b, dtype=float)

    relative_velocity = velocity_a - velocity_b
    impulse_factor = (1.0 + restitution) / (mass_a + mass_b)

    velocity_a_after = velocity_a - impulse_factor * mass_b * relative_velocity
    velocity_b_after = velocity_b + impulse_factor * mass_a * relative_velocity

    kinetic_energy_before = kinetic_energy(mass_a, velocity_a) + kinetic_energy(mass_b, velocity_b)
    kinetic_energy_after = kinetic_energy(mass_a, velocity_a_after) + kinetic_energy(mass_b, velocity_b_after)

    return CollisionResult(
        velocity_a_after=velocity_a_after,
        velocity_b_after=velocity_b_after,
        kinetic_energy_before=kinetic_energy_before,
        kinetic_energy_after=kinetic_energy_after,
    )
