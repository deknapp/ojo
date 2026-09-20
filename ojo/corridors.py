"""Turning "the 2400 block of Zia Road" into something you can draw.

Santa Fe announces enforcement by block, Albuquerque by cross street, and
neither publishes a coordinate. So the geometry has to be reconstructed, and
the reconstruction has three steps, each of which can be checked:

1. Resolve the description to an approximate point -- a geocoded address, or
   the node where two named streets actually meet in OpenStreetMap.
2. Snap that point onto a way that genuinely carries the named street. This
   step is not optional: Nominatim answers `7500 Airport Road` with a point on
   `Old Airport Road`, 500 m away and a different road entirely.
3. Take the run of that street within a fixed distance of the snapped point.

What comes out is a corridor, not a camera. The camera is a trailer that gets
towed. The corridor is the stretch of road where the city said it would be
enforcing, and that is both the more durable claim and the more useful one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import yaml

from .config import CITY_BBOX, CORRIDOR_HALF_LENGTH_M, DATA_DIR
from .fetch import geocode, overpass
from .geometry import Point, snap_to_lines, walk_along

log = logging.getLogger(__name__)


@dataclass
class Corridor:
    id: str
    label: str
    jurisdiction: str
    street: str
    status: str
    enforcement: list[str]
    point: Point
    lines: list[list[Point]]
    maxspeed_mph: int | None
    maxspeed_source: str
    last_confirmed: str | None
    sources: list[dict[str, Any]] = field(default_factory=list)
    note: str | None = None
    snap_distance_m: float | None = None

    def as_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [[[round(lon, 5), round(lat, 5)] for lat, lon in line] for line in self.lines],
            },
            "properties": {
                "id": self.id,
                "label": self.label,
                "jurisdiction": self.jurisdiction,
                "street": self.street,
                "status": self.status,
                "enforcement": self.enforcement,
                "maxspeed_mph": self.maxspeed_mph,
                "maxspeed_source": self.maxspeed_source,
                "last_confirmed": self.last_confirmed,
                "sources": self.sources,
                "note": self.note,
                "anchor": [round(self.point[1], 5), round(self.point[0], 5)],
                "snap_distance_m": round(self.snap_distance_m, 1) if self.snap_distance_m else None,
            },
        }


def _bbox_clause(city: str) -> str:
    south, west, north, east = CITY_BBOX[city]
    return f"({south},{west},{north},{east})"


_DIRECTIONALS = ("north", "south", "east", "west", "n", "s", "e", "w", "nw", "ne", "sw", "se")


def normalise_street(name: str) -> str:
    """`"West Zia Road"` and `"Zia Road"` are the same street. `"Old Airport
    Road"` is not the same street as `"Airport Road"`.

    Only a leading compass word is dropped. Everything else is significant,
    which is the whole point: Santa Fe has both an Airport Road and an Old
    Airport Road, they run within ten metres of each other near Vista Primera,
    and putting a corridor on the wrong one is exactly the class of error this
    tool exists to not make.
    """
    tokens = name.lower().replace(".", "").split()
    while tokens and tokens[0] in _DIRECTIONALS:
        tokens = tokens[1:]
    return " ".join(tokens)


def _ways_named(street: str, city: str) -> tuple[list[list[Point]], list[dict[str, Any]]]:
    """Every drivable way that IS `street`, with geometry.

    Overpass is asked with a loose substring regex, because an exact match on
    "Zia Road" returns nothing at all -- it is mapped as West and East Zia
    Road. The results are then filtered exactly, on the normalised name, so
    the looseness never reaches the output.
    """
    escaped = street.replace('"', '\\"')
    query = (
        f'[out:json][timeout:120];'
        f'way["name"~"{escaped}",i]["highway"]{_bbox_clause(city)};'
        f"out geom tags;"
    )
    wanted = normalise_street(street)
    elements = [
        w for w in overpass(query).get("elements", [])
        if normalise_street(w.get("tags", {}).get("name", "")) == wanted
    ]
    lines = [[(n["lat"], n["lon"]) for n in w.get("geometry", [])] for w in elements]
    keep = [(line, w) for line, w in zip(lines, elements) if len(line) > 1]
    return [line for line, _ in keep], [w for _, w in keep]


def _intersection_point(street: str, other: str, city: str) -> Point | None:
    """The node two named streets share. None if they do not meet in OSM.

    Both sides are name-filtered the same way `_ways_named` filters, so
    "Airport Road at Constellation" cannot quietly resolve against Old Airport
    Road.
    """
    a, b = street.replace('"', '\\"'), other.replace('"', '\\"')
    query = (
        f'[out:json][timeout:120];'
        f'way["name"~"{a}",i]["highway"]{_bbox_clause(city)}->.wa;'
        f'way["name"~"{b}",i]["highway"]{_bbox_clause(city)}->.wb;'
        f"(.wa; .wb;);out ids tags;"
        f"node(w.wa)(w.wb);out;"
    )
    elements = overpass(query).get("elements", [])
    ids = {
        side: {
            w["id"] for w in elements
            if w["type"] == "way" and normalise_street(w.get("tags", {}).get("name", "")) == normalise_street(name)
        }
        for side, name in (("a", street), ("b", other))
    }
    if not ids["a"] or not ids["b"]:
        return None
    nodes = [n for n in elements if n["type"] == "node"]
    if not nodes:
        return None
    # Several shared nodes means a dual carriageway or a slip lane. Their mean
    # is inside the junction, which is the right anchor for a corridor.
    return (
        sum(n["lat"] for n in nodes) / len(nodes),
        sum(n["lon"] for n in nodes) / len(nodes),
    )


def parse_maxspeed(value: str | None) -> int | None:
    """`"35 mph"` and `"30"` both mean 30-odd mph. Anything else means nothing."""
    if not value:
        return None
    token = value.strip().lower().removesuffix("mph").strip()
    try:
        return int(float(token))
    except ValueError:
        return None


def _maxspeed_near(point: Point, lines: list[list[Point]], ways: list[dict[str, Any]]) -> tuple[int | None, str]:
    """The posted limit on the nearest tagged piece of this street, if any.

    OSM has `maxspeed` on about a fifth of Santa Fe's drivable ways, so this
    returns None often. It returns None rather than a neighbouring street's
    number, and the site says "not in the data -- read the signs" when it does.
    """
    tagged = [(line, w) for line, w in zip(lines, ways) if parse_maxspeed(w.get("tags", {}).get("maxspeed"))]
    if not tagged:
        return None, "absent from OpenStreetMap"
    _, distance, index = snap_to_lines(point, [line for line, _ in tagged])
    if distance > 200.0:
        return None, "absent from OpenStreetMap"
    return parse_maxspeed(tagged[index][1]["tags"]["maxspeed"]), "OpenStreetMap"


def build_santa_fe() -> tuple[list[Corridor], dict[str, Any]]:
    """Every curated Santa Fe location, as drawable corridors."""
    spec = yaml.safe_load((DATA_DIR / "santa_fe.yaml").read_text())
    corridors: list[Corridor] = []

    for entry in spec["locations"]:
        street = entry["street"]
        lines, ways = _ways_named(street, "Santa Fe")
        if not lines:
            log.warning("no OSM way named %r; skipping %s", street, entry["id"])
            continue

        if entry.get("intersection_with"):
            anchor = _intersection_point(street, entry["intersection_with"], "Santa Fe")
            if anchor is None:
                log.warning("no intersection of %r and %r", street, entry["intersection_with"])
                continue
            snap_distance = 0.0
        else:
            anchor = geocode(entry["geocode_query"])
            if anchor is None:
                log.warning("geocode failed for %r", entry["geocode_query"])
                continue
            anchor, snap_distance, _ = snap_to_lines(anchor, lines)

        segments = walk_along(lines, anchor, CORRIDOR_HALF_LENGTH_M)
        if not segments:
            log.warning("no geometry within corridor radius for %s", entry["id"])
            continue

        limit, limit_source = _maxspeed_near(anchor, lines, ways)
        corridors.append(
            Corridor(
                id=entry["id"],
                label=entry["label"],
                jurisdiction="Santa Fe",
                street=street,
                status=entry["status"],
                enforcement=entry.get("enforcement", ["speed"]),
                point=anchor,
                lines=segments,
                maxspeed_mph=limit,
                maxspeed_source=limit_source,
                last_confirmed=str(entry.get("last_confirmed")) if entry.get("last_confirmed") else None,
                sources=entry.get("sources", []),
                note=entry.get("note"),
                snap_distance_m=snap_distance,
            )
        )

    return corridors, spec
