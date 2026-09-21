"""The city's road network, and where its streets meet.

Everything here reads from the local extract (see ojo/extract.py). There is
no network call in this module and no rate limit to respect, which is the
whole reason the extract exists.

Junctions are found by exact coordinate match. Two OpenStreetMap ways that
cross at an intersection share a node, and a shared node is the same
coordinate to the last decimal place in both ways, so comparing rounded
vertices finds junctions without needing node ids or a spatial index. The
result is checkable: the junctions this computes for Albuquerque land within
about 10 m of the camera nodes volunteers mapped at the same intersections.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import CITY_BBOX
from .extract import ways_in
from .geometry import Point

log = logging.getLogger(__name__)

#: Coordinate rounding for junction detection. Seven decimal places is about a
#: centimetre -- far tighter than any real road, and exactly how OSM stores a
#: shared node in both of the ways that use it.
JUNCTION_PRECISION = 7


@dataclass
class RoadNetwork:
    city: str
    ways: list[dict[str, Any]]
    lines: list[list[Point]]
    _by_vertex: dict[tuple[float, float], set[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        index: dict[tuple[float, float], set[int]] = defaultdict(set)
        for i, line in enumerate(self.lines):
            for lat, lon in line:
                index[(round(lat, JUNCTION_PRECISION), round(lon, JUNCTION_PRECISION))].add(i)
        self._by_vertex = index

    def indices_where(self, predicate) -> list[int]:
        return [i for i, w in enumerate(self.ways) if predicate(w.get("tags", {}).get("name", ""))]

    def geometry(self, indices: Iterable[int]) -> tuple[list[list[Point]], list[dict[str, Any]]]:
        indices = list(indices)
        return [self.lines[i] for i in indices], [self.ways[i] for i in indices]

    def junction(self, a: list[int], b: list[int]) -> Point | None:
        """Mean of the vertices shared between two sets of ways."""
        set_a, set_b = set(a), set(b)
        shared = [
            vertex
            for vertex, owners in self._by_vertex.items()
            if owners & set_a and owners & set_b
        ]
        if not shared:
            return None
        return (
            sum(v[0] for v in shared) / len(shared),
            sum(v[1] for v in shared) / len(shared),
        )


def fetch(city: str, names: Iterable[str] | None = None) -> RoadNetwork:
    """Every named drivable way in `city`.

    `names` is accepted and ignored. It mattered when each name cost a
    request; now the whole city is already in memory, and filtering by name
    is a list comprehension in the caller.
    """
    ways = ways_in(CITY_BBOX[city])
    lines = [[(lat, lon) for lat, lon in w["geometry"]] for w in ways]
    log.info("%s: %d named drivable ways", city, len(ways))
    return RoadNetwork(city=city, ways=ways, lines=lines)
