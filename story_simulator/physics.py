"""Collision detection over the registry's position/dimensions/mass components.

Every entity with both `position` and `dimensions` is an axis-aligned box:
centered on its position in x and y, resting on it in z (see `dimensions`'
description in manifest/builtins.yaml). One that also has `mass` is a solid
body; one without is a region (a parking spot, a street, ...). Two solid
bodies collide when their boxes overlap; a body is inside a region when its
box lies entirely within the region's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from emc2p.registrar import Registrar

_FIELDS = ["position.x", "position.y", "position.z", "dimensions.x", "dimensions.y", "dimensions.z"]


@dataclass(frozen=True)
class Body:
    alias: str
    position: tuple[float, float, float]
    dimensions: tuple[float, float, float]
    solid: bool

    def bounds(self) -> list[tuple[float, float]]:
        """(low, high) extent along x, y, z."""
        (x, y, z), (dx, dy, dz) = self.position, self.dimensions
        return [(x - dx / 2, x + dx / 2), (y - dy / 2, y + dy / 2), (z, z + dz)]


def collides(a: Body, b: Body) -> bool:
    """True if two solid bodies overlap (touching doesn't count)."""
    if not (a.solid and b.solid):
        return False
    return all(alo < bhi and blo < ahi for (alo, ahi), (blo, bhi) in zip(a.bounds(), b.bounds()))


def inside(body: Body, region: Body) -> bool:
    """True if `body`'s whole box lies within `region`'s."""
    if region.solid:
        return False
    return all(rlo <= lo and hi <= rhi for (lo, hi), (rlo, rhi) in zip(body.bounds(), region.bounds()))


def load_bodies(registrar: Registrar) -> dict[str, Body]:
    """Every entity with a current position and dimensions, keyed by alias."""
    df = registrar.safe_view_current(_FIELDS).to_pandas()
    df = df.dropna(subset=[f for f in _FIELDS if f != "position.z"])
    massive = set(registrar.safe_view_current("mass.value").to_pandas().get("entity_id.alias", []))
    bodies = {}
    for _, row in df.iterrows():
        z = 0.0 if math.isnan(row["position.z"]) else row["position.z"]
        alias = row["entity_id.alias"]
        bodies[alias] = Body(
            alias=alias,
            position=(row["position.x"], row["position.y"], z),
            dimensions=(row["dimensions.x"], row["dimensions.y"], row["dimensions.z"]),
            solid=alias in massive,
        )
    return bodies


def check_collisions(
    registrar: Registrar, alias: str, x: float | None = None, y: float | None = None, z: float | None = None
) -> dict:
    """What `alias` collides with and is inside, at its current position or a hypothetical one.

    Any of x/y/z given overrides that coordinate of the current position --
    e.g. pass a parking spot's position to ask "would this car fit there?"
    before writing it. `alias` itself is never reported against itself.
    """
    bodies = load_bodies(registrar)
    if alias not in bodies:
        raise ValueError(f"{alias!r} has no current position and dimensions.")
    body = bodies[alias]
    cx, cy, cz = body.position
    body = Body(alias, (cx if x is None else x, cy if y is None else y, cz if z is None else z), body.dimensions, body.solid)
    others = [b for a, b in bodies.items() if a != alias]
    return {
        "alias": alias,
        "position": list(body.position),
        "collides_with": sorted(b.alias for b in others if collides(body, b)),
        "inside": sorted(b.alias for b in others if inside(body, b)),
    }
