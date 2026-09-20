"""One road download per city, then everything else is local.

The naive way to place forty Albuquerque cameras is forty-odd Overpass
queries, one per street name. That does not work: a case-insensitive regex on
`name` across the city box is expensive, the public instance answers about
half of them with a 504, and retrying politely still takes longer than the
data is worth.

So streets are fetched once, in a single query whose regex is the alternation
of every name the build actually needs, and the rest -- which ways are really
"Gibson", where Gibson meets Carlisle -- is computed here from the geometry.

Junctions are found by exact coordinate match. Two OpenStreetMap ways that
cross at an intersection share a node, and a shared node is the same
coordinate to the last decimal place in both ways, so comparing rounded
vertices finds junctions without needing node ids or a spatial index.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import CITY_BBOX
from .fetch import overpass
from .geometry import Point

log = logging.getLogger(__name__)

DRIVABLE = "motorway|trunk|primary|secondary|tertiary|residential|unclassified|motorway_link|trunk_link|primary_link|secondary_link"

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


#: Overpass matches bytes, so a stem taken from the city's accent-free list
#: ("Montano", "Cesar") never matches the accented name OpenStreetMap stores
#: ("Montaño", "César"). Each letter that might carry an accent becomes a
#: character class instead.
ACCENTS = {
    "a": "aáàâä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôö",
    "u": "uúùûü", "n": "nñ", "c": "cç",
}


def accent_tolerant(stem: str) -> str:
    """A regex for `stem` that matches its accented spellings too."""
    out = []
    for char in stem:
        expanded = ACCENTS.get(char.lower())
        out.append(f"[{expanded}]" if expanded else re.escape(char))
    return "".join(out)


def fetch(city: str, names: Iterable[str]) -> RoadNetwork:
    """Download every drivable way in `city` whose name starts with one of `names`."""
    south, west, north, east = CITY_BBOX[city]
    stems = sorted({n.strip() for n in names if n and n.strip()})
    if not stems:
        raise ValueError("no street names requested")
    pattern = "^(" + "|".join(accent_tolerant(s) for s in stems) + ")"
    query = (
        f"[out:json][timeout:180];"
        f'way["highway"~"^({DRIVABLE})$"]["name"~"{pattern}",i]'
        f"({south},{west},{north},{east});"
        f"out geom tags;"
    )
    elements = [w for w in overpass(query).get("elements", []) if len(w.get("geometry", [])) > 1]
    lines = [[(n["lat"], n["lon"]) for n in w["geometry"]] for w in elements]
    log.info("%s: %d ways for %d name stems", city, len(elements), len(stems))
    return RoadNetwork(city=city, ways=elements, lines=lines)
