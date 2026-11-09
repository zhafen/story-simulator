"""Collision detection over the registry's position/radius/mass components.

Every entity with both `position` and `radius` is a sphere. One that also
has `mass` is a solid body; one without is a region (a parking spot, a
street, ...). Two solid bodies collide when their spheres overlap; a body
is inside a region when its whole sphere fits within the region's. See
`radius`'s description in manifest/builtins.yaml.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from emc2p.registrar import Registrar


@dataclass(frozen=True)
class Body:
    alias: str
    position: tuple[float, float, float]
    radius: float
    solid: bool


def collides(a: Body, b: Body) -> bool:
    """True if two solid bodies overlap (touching doesn't count)."""
    return a.solid and b.solid and math.dist(a.position, b.position) < a.radius + b.radius


def inside(body: Body, region: Body) -> bool:
    """True if `body`'s whole sphere lies within `region`'s."""
    return not region.solid and math.dist(body.position, region.position) + body.radius <= region.radius


def load_bodies(registrar: Registrar) -> dict[str, Body]:
    """Every entity with a current position and radius, keyed by alias."""
    df = registrar.safe_view_current(["position.x", "position.y", "position.z", "radius.value"]).to_pandas()
    df = df.dropna(subset=["position.x", "position.y", "radius.value"])
    massive = set(registrar.safe_view_current("mass.value").to_pandas().get("entity_id.alias", []))
    return {
        row["entity_id.alias"]: Body(
            alias=row["entity_id.alias"],
            position=(row["position.x"], row["position.y"], 0.0 if math.isnan(row["position.z"]) else row["position.z"]),
            radius=row["radius.value"],
            solid=row["entity_id.alias"] in massive,
        )
        for _, row in df.iterrows()
    }


def check_collisions(
    registrar: Registrar, alias: str, x: float | None = None, y: float | None = None, z: float | None = None
) -> dict:
    """What `alias` collides with and is inside, at its current position or a hypothetical one.

    Any of x/y/z given overrides that coordinate of the current position --
    e.g. pass a parking spot's center to ask "would this car fit there?"
    before writing it. `alias` itself is never reported against itself.
    """
    bodies = load_bodies(registrar)
    if alias not in bodies:
        raise ValueError(f"{alias!r} has no current position and radius.")
    body = bodies[alias]
    cx, cy, cz = body.position
    body = Body(alias, (cx if x is None else x, cy if y is None else y, cz if z is None else z), body.radius, body.solid)
    others = [b for a, b in bodies.items() if a != alias]
    return {
        "alias": alias,
        "position": list(body.position),
        "collides_with": sorted(b.alias for b in others if collides(body, b)),
        "inside": sorted(b.alias for b in others if inside(body, b)),
    }
