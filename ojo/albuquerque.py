"""Albuquerque publishes its list. Parsing it is the whole job.

This is the only official, current, city-published record of automated
enforcement locations in New Mexico, and it is a bulleted list of English
sentences on a web page:

    Gibson between Carlisle and San Mateo (eastbound), live 4/25/2022.
    Eubank just north of Central (northbound), live 4/26/2023.
    Coors north of St. Joseph (southbound), 7/29/2026.

Four things make that worth parsing rather than transcribing. It is kept
current -- the newest entry is days old. It is directional, so a route that
uses the other side of the road does not cross it. It carries an activation
date, which makes the list a four-year record of where a city chose to put
cameras. And it is the counter-example to Santa Fe: proof that a city can
just publish this.
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import yaml

from .config import ABQ_LIST_URL, DATA_DIR, FIXED_CORRIDOR_HALF_LENGTH_M
from .corridors import Corridor, _maxspeed_near
from .fetch import cached_json, geocode, get
from .geometry import distance_m, snap_to_lines, walk_along
from .network import RoadNetwork, fetch as fetch_network

log = logging.getLogger(__name__)

ROAD_TYPES = {
    "boulevard", "avenue", "road", "street", "drive", "lane", "trail",
    "way", "place", "court", "bypass", "parkway", "circle",
}
QUADRANTS = {"northeast", "northwest", "southeast", "southwest", "ne", "nw", "se", "sw"}

#: The relational phrases the city uses between a street and its cross street.
RELATION = r"just north of|just south of|just east of|just west of|north of|south of|east of|west of"

#: "Gibson between Carlisle and San Mateo (eastbound), live 4/25/2022."
ENTRY = re.compile(
    r"^(?P<body>.+?)\s*\((?P<direction>north|south|east|west)bound\)\s*,\s*"
    r"(?:live\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
BETWEEN = re.compile(r"^(?P<street>.+?)\s+between\s+(?P<a>.+?)\s+and\s+(?P<b>.+?)$", re.IGNORECASE)
RELATIVE = re.compile(r"^(?P<street>.+?)\s+(?:at|and|near|" + RELATION + r")\s+(?P<cross>.+?)$", re.IGNORECASE)

#: "Unser at Flor Del Sol just north of Dellyne" names the junction twice. The
#: first cross street is the one that locates it; the rest is colour, and
#: leaving it in makes the cross street unfindable.
TRAILING_RELATION = re.compile(r"\s+(?:" + RELATION + r"|at|and|near)\s+.*$", re.IGNORECASE)

#: "Wyoming and just north of Academy" puts the relation after the connector
#: rather than before it, so it survives into the cross street.
LEADING_RELATION = re.compile(r"^(?:just\s+)?(?:" + RELATION + r"|just)\s+", re.IGNORECASE)


@dataclass
class Announcement:
    street: str
    cross: list[str]
    direction: str
    live: str
    raw: str


def strip_accents(text: str) -> str:
    """`"Avenida César Chávez"` and `"Avenida Cesar Chavez"` are one street.

    The city writes its list without accents and OpenStreetMap writes the
    street with them, so a byte comparison finds nothing. Three real
    Albuquerque camera sites turn on this.
    """
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalise_abq(name: str) -> str:
    """Drop a trailing quadrant, lowercase, strip accents and punctuation."""
    tokens = strip_accents(name).lower().replace(".", "").replace(",", "").replace("'", "").split()
    while tokens and tokens[-1] in QUADRANTS:
        tokens = tokens[:-1]
    return " ".join(tokens)


def matches_street(osm_name: str, announced: str) -> bool:
    """Is this OSM way the street the city meant?

    True when the names agree once the quadrant is dropped, or when the OSM
    name is the announced name plus exactly one road-type word. That second
    rule is what lets "Gibson" find "Gibson Boulevard Southeast" while still
    refusing "Coors Boulevard Bypass" for "Coors" -- a real distinction in
    Albuquerque, where both carry cameras and they are different roads.
    """
    osm, want = normalise_abq(osm_name), normalise_abq(announced)
    if not osm or not want:
        return False
    if osm == want:
        return True
    extra = osm.removeprefix(want + " ").split() if osm.startswith(want + " ") else []
    return len(extra) == 1 and extra[0] in ROAD_TYPES


def parse_date(text: str) -> str:
    month, day, year = text.split("/")
    year = f"20{year}" if len(year) == 2 else year
    return f"{year}-{int(month):02d}-{int(day):02d}"


def fetch_list() -> list[str]:
    """The published bullets, as text."""

    def produce() -> list[str]:
        page = get(ABQ_LIST_URL, timeout=90).decode("utf-8", "replace")
        page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
        text = html.unescape(re.sub(r"<[^>]+>", "\n", page))
        found = re.findall(
            r"([A-Za-z0-9][^\n]{5,110}?\((?:north|south|east|west)bound\)[^\n]{0,40})", text, re.IGNORECASE
        )
        seen, out = set(), []
        for line in (" ".join(f.split()) for f in found):
            if line not in seen:
                seen.add(line)
                out.append(line)
        return out

    return cached_json("abq", ABQ_LIST_URL, produce)  # type: ignore[return-value]


def parse(lines: list[str]) -> tuple[list[Announcement], list[str]]:
    """Announcements, and the lines that could not be parsed."""
    parsed, unparsed = [], []
    for line in lines:
        match = ENTRY.match(line)
        if not match:
            unparsed.append(line)
            continue
        body = match.group("body").strip()
        if between := BETWEEN.match(body):
            street, cross = between.group("street"), [between.group("a"), between.group("b")]
        elif relative := RELATIVE.match(body):
            street, cross = relative.group("street"), [relative.group("cross")]
        else:
            unparsed.append(line)
            continue
        parsed.append(
            Announcement(
                street=street.strip(),
                cross=[TRAILING_RELATION.sub("", LEADING_RELATION.sub("", c.strip())).strip() for c in cross],
                direction=match.group("direction").lower() + "bound",
                live=parse_date(match.group("date")),
                raw=line,
            )
        )
    return parsed, unparsed


def _aliases() -> dict[str, str]:
    return yaml.safe_load((DATA_DIR / "albuquerque_aliases.yaml").read_text())["aliases"]


def _stem(name: str, alias: dict[str, str]) -> str:
    """The name to look for in OSM, aliases applied."""
    return alias.get(name, name)


def _indices(network: RoadNetwork, name: str, alias: dict[str, str]) -> list[int]:
    """Way indices that are this street.

    Matched with `matches_street`, so "Gibson" finds "Gibson Boulevard
    Southeast" and does not find "Gibson Court".
    """
    wanted = _stem(name, alias)
    return network.indices_where(lambda osm, w=wanted: matches_street(osm, w))


def street_names(announcements: list[Announcement], alias: dict[str, str]) -> set[str]:
    """Every name the road download has to cover, as first-word stems.

    Stems rather than full names because OSM spells out what the city
    abbreviates, and a stem is the cheapest regex that is guaranteed to
    include the real name.
    """
    names: set[str] = set()
    for a in announcements:
        for raw in [a.street, *a.cross]:
            names.add(strip_accents(_stem(raw, alias)).split()[0])
    return names


def build(limit: int | None = None) -> tuple[list[Corridor], list[str]]:
    """Every Albuquerque announcement that resolves to geometry, plus the rest.

    The second return value matters as much as the first. A camera this code
    could not place is not a camera that is not there, and the build prints
    them rather than letting the map imply that stretch is unenforced.
    """
    alias = _aliases()
    announcements, unresolved = parse(fetch_list())
    announcements = announcements[:limit]
    network = fetch_network("Albuquerque", street_names(announcements, alias))
    corridors: list[Corridor] = []

    for announcement in announcements:
        own = _indices(network, announcement.street, alias)
        if not own:
            unresolved.append(f"{announcement.raw} [no OSM way matching {announcement.street!r}]")
            continue
        lines, ways = network.geometry(own)

        crossings = []
        for cross in announcement.cross:
            other = _indices(network, cross, alias)
            point = network.junction(own, other) if other else None
            if point is None:
                # Some cross streets are not in the download at all, and some
                # are named so differently that no junction is found. Falling
                # back to the geocoder and snapping onto the announced street
                # recovers them; the snap is what keeps the fallback honest,
                # since a geocoder miss lands on the road or it does not land.
                located = geocode(f"{_stem(cross, alias)}, Albuquerque, NM")
                if located is None:
                    continue
                snapped, distance, _ = snap_to_lines(located, lines)
                if distance > 400.0:
                    continue
                point = snapped
            crossings.append(snap_to_lines(point, lines)[0])

        if not crossings:
            unresolved.append(f"{announcement.raw} [{announcement.street} does not meet {announcement.cross}]")
            continue

        if len(crossings) == 2:
            anchor = ((crossings[0][0] + crossings[1][0]) / 2, (crossings[0][1] + crossings[1][1]) / 2)
            radius = max(distance_m(*crossings) / 2, FIXED_CORRIDOR_HALF_LENGTH_M)
        else:
            anchor, radius = crossings[0], FIXED_CORRIDOR_HALF_LENGTH_M

        segments = walk_along(lines, anchor, radius)
        if not segments:
            unresolved.append(f"{announcement.raw} [no geometry within {radius:.0f} m of the anchor]")
            continue

        speed, speed_source = _maxspeed_near(anchor, lines, ways)
        corridors.append(
            Corridor(
                id="abq-" + re.sub(r"[^a-z0-9]+", "-", announcement.raw.lower())[:48].strip("-"),
                label=announcement.raw.rstrip("."),
                jurisdiction="Albuquerque",
                street=announcement.street,
                status="active",
                enforcement=["speed"],
                point=anchor,
                lines=segments,
                maxspeed_mph=speed,
                maxspeed_source=speed_source,
                last_confirmed=announcement.live,
                sources=[{"url": ABQ_LIST_URL, "retrieved": "2026-09-20", "note": "city-published list"}],
                note=f"{announcement.direction}; live since {announcement.live}",
            )
        )

    return corridors, unresolved
