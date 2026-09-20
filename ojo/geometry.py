"""Small geodesy. No dependencies, because none of this needs them.

Distances here are local and short -- a few hundred metres on a city street --
so an equirectangular approximation about the local latitude is accurate to far
better than the width of the road, and is easier to check by hand than a
projection library would be.
"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0

Point = tuple[float, float]  # (lat, lon)


def metres_per_degree(lat: float) -> tuple[float, float]:
    """Metres per degree of latitude and of longitude, at this latitude."""
    per_lat = math.pi * EARTH_RADIUS_M / 180.0
    per_lon = per_lat * math.cos(math.radians(lat))
    return per_lat, per_lon


def distance_m(a: Point, b: Point) -> float:
    per_lat, per_lon = metres_per_degree((a[0] + b[0]) / 2.0)
    return math.hypot((a[0] - b[0]) * per_lat, (a[1] - b[1]) * per_lon)


def _project_onto_segment(p: Point, a: Point, b: Point) -> tuple[Point, float]:
    """Closest point to `p` on segment a-b, and the distance to it in metres."""
    per_lat, per_lon = metres_per_degree(p[0])
    ax, ay = a[1] * per_lon, a[0] * per_lat
    bx, by = b[1] * per_lon, b[0] * per_lat
    px, py = p[1] * per_lon, p[0] * per_lat
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return a, distance_m(p, a)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    closest = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return closest, distance_m(p, closest)


def snap_to_lines(p: Point, lines: list[list[Point]]) -> tuple[Point, float, int]:
    """Snap `p` onto the nearest of several polylines.

    Returns the snapped point, the distance to it in metres, and the index of
    the line it landed on. This is what keeps a geocoder's near-miss from
    putting an enforcement corridor on the wrong street.
    """
    best: tuple[Point, float, int] | None = None
    for index, line in enumerate(lines):
        for a, b in zip(line, line[1:]):
            point, distance = _project_onto_segment(p, a, b)
            if best is None or distance < best[1]:
                best = (point, distance, index)
    if best is None:
        raise ValueError("no lines to snap to")
    return best


def walk_along(lines: list[list[Point]], origin: Point, half_length_m: float) -> list[list[Point]]:
    """Every piece of `lines` within `half_length_m` of `origin`, along the road.

    Measured as crow-flies distance from the origin rather than as path
    distance. On a city street the two agree closely, and the difference is
    swamped by the fact that the published location is a block, not a point.
    """
    out: list[list[Point]] = []
    for line in lines:
        run: list[Point] = []
        for point in line:
            if distance_m(point, origin) <= half_length_m:
                run.append(point)
            elif len(run) > 1:
                out.append(run)
                run = []
            else:
                run = []
        if len(run) > 1:
            out.append(run)
    return out
