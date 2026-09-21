"""Rio Rancho, from OpenStreetMap, because Rio Rancho does not publish a list.

Somebody mapped sixteen Rio Rancho cameras in December 2025, with the street,
the direction and the posted limit on each node. That is a community record,
not an official one, and it is treated accordingly: every corridor built here
carries the OSM node id, the mapper's last-edit date, and a `check_date` when
the mapper recorded one, so a reader can judge its age themselves.

The same query covers Albuquerque, where it serves a different purpose -- a
cross-check against the city's own list. Where the two disagree, the city's
list wins and the disagreement is worth looking at.
"""

from __future__ import annotations

import logging
from typing import Any

from .config import CITY_BBOX, FIXED_CORRIDOR_HALF_LENGTH_M
from .corridors import Corridor, parse_maxspeed
from .network import fetch as fetch_network
from .extract import cameras_in
from .geometry import Point, snap_to_lines, walk_along

log = logging.getLogger(__name__)


def _nodes(city: str) -> list[dict[str, Any]]:
    return cameras_in(CITY_BBOX[city])


def _roads(city: str) -> tuple[list[list[Point]], list[dict[str, Any]]]:
    """Every named drivable way in the city, from the local extract."""
    network = fetch_network(city)
    return network.lines, network.ways


def build(city: str) -> list[Corridor]:
    """Corridors for every mapped speed camera in `city`."""
    corridors: list[Corridor] = []
    nodes = _nodes(city)
    if not nodes:
        return corridors
    lines, ways = _roads(city)
    if not lines:
        log.warning("no roads near any camera in %s", city)
        return corridors

    for node in nodes:
        tags = node.get("tags", {})
        point = (node["lat"], node["lon"])
        _, distance, index = snap_to_lines(point, lines)
        if distance > 60.0:
            log.warning("no road within 60 m of OSM node %s", node["id"])
            continue
        street = ways[index].get("tags", {}).get("name", "unnamed road")
        segments = walk_along([lines[index]], point, FIXED_CORRIDOR_HALF_LENGTH_M)
        if not segments:
            segments = [lines[index]]

        limit = parse_maxspeed(tags.get("maxspeed")) or parse_maxspeed(ways[index].get("tags", {}).get("maxspeed"))
        checked = tags.get("check_date")
        edited = (node.get("timestamp") or "")[:10]
        corridors.append(
            Corridor(
                id=f"osm-{node['id']}",
                label=tags.get("ref") or f"{street} speed camera",
                jurisdiction=city,
                street=street,
                status="community-mapped",
                enforcement=["speed"],
                point=point,
                lines=segments,
                maxspeed_mph=limit,
                maxspeed_source="OpenStreetMap" if limit else "absent from OpenStreetMap",
                last_confirmed=checked or edited or None,
                sources=[
                    {
                        "url": f"https://www.openstreetmap.org/node/{node['id']}",
                        "retrieved": "2026-09-20",
                        "note": (
                            f"mapped by {node.get('user', 'unknown')}, last edited {edited}"
                            + (f", surveyed {checked}" if checked else "")
                        ),
                    }
                ],
                note=(
                    "Community-mapped, not published by the city. "
                    + ("Surveyed " + checked if checked else "No survey date recorded")
                ),
                snap_distance_m=0.0,
            )
        )
    return corridors
