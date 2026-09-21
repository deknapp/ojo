"""Roads and camera nodes from a local OpenStreetMap extract.

This project used to read road geometry from the Overpass API, and the
experience is worth recording because it changed the design. A build needs a
few dozen queries; rebuilding from a cold cache got this address rate-limited
and then refused outright by the main instance, and every public mirror was
either busy, broken, or -- worse -- answering with empty results that look
exactly like "there are no cameras here".

A rate limit is a signal that the tool is asking the wrong question. The road
network of New Mexico is one file, it changes slowly, and Geofabrik publishes
it daily. Downloading it once makes the build reproducible offline, removes
every timeout and mirror from the critical path, and turns forty queries into
a single pass over a local file.

Nominatim is still called for geocoding, at one request per second with the
results cached, because there is no comparable offline substitute and the
volume is a few dozen addresses.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Any, Iterable

import osmium

from .config import BBOX, CACHE_DIR, EXTRACT_URL, USER_AGENT

log = logging.getLogger(__name__)

EXTRACT_PATH = CACHE_DIR / "new-mexico-latest.osm.pbf"

DRIVABLE = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "unclassified", "motorway_link", "trunk_link",
    "primary_link", "secondary_link", "tertiary_link", "living_street",
}


def ensure_extract(path: Path = EXTRACT_PATH) -> Path:
    """Download the New Mexico extract if it is not already here."""
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("downloading %s", EXTRACT_URL)
    request = urllib.request.Request(EXTRACT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=900) as response, path.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    log.info("extract is %.1f MB", path.stat().st_size / 1e6)
    return path


def _in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    south, west, north, east = bbox
    return south <= lat <= north and west <= lon <= east


def read(bbox: tuple[float, float, float, float] = BBOX) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Named drivable ways and speed-camera nodes inside `bbox`.

    Returns ways in the same shape Overpass produced -- `{"id", "tags",
    "geometry"}` -- so nothing downstream had to change when the source did.
    """
    path = ensure_extract()
    ways: list[dict[str, Any]] = []
    cameras: list[dict[str, Any]] = []

    processor = osmium.FileProcessor(str(path)).with_locations().with_filter(
        osmium.filter.KeyFilter("highway")
    )
    for obj in processor:
        if obj.is_node():
            if obj.tags.get("highway") == "speed_camera" and _in_bbox(obj.location.lat, obj.location.lon, bbox):
                cameras.append(
                    {
                        "id": obj.id,
                        "lat": obj.location.lat,
                        "lon": obj.location.lon,
                        "tags": dict(obj.tags),
                        "timestamp": obj.timestamp.isoformat() if obj.timestamp else "",
                        "user": obj.user or "",
                    }
                )
            continue
        if not obj.is_way():
            continue
        if obj.tags.get("highway") not in DRIVABLE or not obj.tags.get("name"):
            continue
        try:
            geometry = [(n.lat, n.lon) for n in obj.nodes if n.location.valid()]
        except osmium.InvalidLocationError:
            continue
        if len(geometry) < 2 or not any(_in_bbox(lat, lon, bbox) for lat, lon in geometry):
            continue
        ways.append({"id": obj.id, "tags": dict(obj.tags), "geometry": geometry})

    log.info("extract: %d named drivable ways, %d speed cameras in the study area", len(ways), len(cameras))
    return ways, cameras


_CACHE: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}


def load(bbox: tuple[float, float, float, float] = BBOX):
    """`read`, memoised for the life of the process."""
    key = repr(bbox)
    if key not in _CACHE:
        _CACHE[key] = read(bbox)
    return _CACHE[key]


def ways_in(bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    ways, _ = load()
    return [w for w in ways if any(_in_bbox(lat, lon, bbox) for lat, lon in w["geometry"])]


def cameras_in(bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    _, cameras = load()
    return [c for c in cameras if _in_bbox(c["lat"], c["lon"], bbox)]
