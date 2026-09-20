"""Schools, because the threshold halves next to them.

Outside a school or construction zone, Santa Fe cites at more than 10 mph over
and the fine is $50. Inside one, it cites at more than 5 mph over and the fine
is $100 -- twice the money at half the margin. For a driver trying not to get a
ticket, that is the single highest-risk category per mile, so the map has to
show it.

What this module can honestly provide is where the schools are. It cannot
provide where the zones are, and the distinction is not pedantry:

    NMSA 1978 66-7-301 caps speed at 15 mph "when passing a school while
    children are going to or leaving school and when the school zone is
    properly posted."

Three conditions. The third is a fact about signs, and signs are in no
dataset -- not the city's, not the state's, not OpenStreetMap's, which has
exactly zero school-zone objects in Santa Fe. So this draws a plain radius
around each school and the site labels it "school nearby -- watch for a posted
zone". It is a prompt to look up, not a boundary.

Source is the NCES public-school universe, republished as a feature service:
authoritative for location, silent about zones.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

from .config import BBOX, SCHOOL_PROXIMITY_M, SCHOOLS_FEATURE_SERVICE
from .fetch import cached_json, get
from .geometry import Point, distance_m

log = logging.getLogger(__name__)

PAGE = 1000

#: Schools with no building a child walks to have no school zone. These are
#: matched on name because the dataset has no "virtual" flag.
NOT_PHYSICAL = ("CONNECTIONS ACADEMY", "VIRTUAL ACADEMY", "ONLINE", "HOMESCHOOL", "CYBER")


@dataclass
class School:
    name: str
    city: str
    street: str
    point: Point

    def as_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(self.point[1], 5), round(self.point[0], 5)]},
            "properties": {
                "name": self.name.title(),
                "city": self.city.title(),
                "street": self.street.title(),
                "radius_m": SCHOOL_PROXIMITY_M,
            },
        }


def fetch() -> list[School]:
    """Every public school inside the study area, with coordinates."""
    south, west, north, east = BBOX
    out: list[School] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "NAME,STREET,CITY,NCESSCH,SCHOOLYEAR",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultOffset": str(offset),
            "resultRecordCount": str(PAGE),
        }
        url = f"{SCHOOLS_FEATURE_SERVICE}?{urllib.parse.urlencode(params)}"
        payload = cached_json("schools", url, lambda u=url: json.loads(get(u, timeout=120)))
        features = payload.get("features", [])  # type: ignore[union-attr]
        for feature in features:
            attributes, geometry = feature["attributes"], feature.get("geometry") or {}
            if geometry.get("y") is None or geometry.get("x") is None:
                continue
            name = (attributes.get("NAME") or "").strip()
            if any(token in name.upper() for token in NOT_PHYSICAL):
                continue
            out.append(
                School(
                    name=name,
                    city=(attributes.get("CITY") or "").strip(),
                    street=(attributes.get("STREET") or "").strip(),
                    point=(float(geometry["y"]), float(geometry["x"])),
                )
            )
        if not payload.get("exceededTransferLimit") or not features:  # type: ignore[union-attr]
            break
        offset += PAGE
    return out


def near(point: Point, schools: list[School], radius_m: float = SCHOOL_PROXIMITY_M) -> list[School]:
    """Schools within `radius_m` of a point."""
    return [s for s in schools if distance_m(point, s.point) <= radius_m]


def flag_corridors(corridors, schools: list[School]) -> int:
    """Mark every corridor that runs past a school. Returns how many.

    A corridor is flagged if ANY point on its drawn geometry is close to a
    school, not just its anchor: the threshold applies where the sign is, and
    a 600 m corridor can start outside a zone and end inside one.
    """
    flagged = 0
    for corridor in corridors:
        hits = {
            school.name.title()
            for line in corridor.lines
            for vertex in line
            for school in near(vertex, schools)
        }
        corridor.schools_nearby = sorted(hits)  # type: ignore[attr-defined]
        if hits:
            flagged += 1
    return flagged
