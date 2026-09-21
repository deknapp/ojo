"""Assemble everything into the three files the site reads.

The site is static. It has no backend, it computes nothing at request time,
and it can be served from a bucket -- so the whole build happens here and the
output is small enough to read in a text editor if you doubt it.

Three files:

* `corridors.geojson` -- every enforcement corridor, with its provenance, the
  threshold that applies, and the date the location was last confirmed.
* `schools.geojson` -- school points, for the halved threshold.
* `meta.json` -- fines, thresholds, build date, and the list of announcements
  that could NOT be placed, which the site shows rather than hides.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

import yaml

from .config import DATA_DIR, SCHOOL_PROXIMITY_M, SITE_DATA_DIR
from .corridors import Corridor, build_santa_fe
from .geometry import distance_m

log = logging.getLogger(__name__)

def _json_default(value: Any) -> str:
    """YAML gives back real dates; JSON wants strings."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


#: An OSM-mapped camera this close to an officially published corridor is the
#: same camera seen twice. The city's record wins, and the duplicate is
#: dropped rather than drawn as a second enforcement zone.
DUPLICATE_RADIUS_M = 250.0


def deduplicate(official: list[Corridor], community: list[Corridor]) -> tuple[list[Corridor], int]:
    """Drop community-mapped cameras that an official list already covers.

    Compared against the official corridor's whole geometry, not its anchor.
    "Gibson between Carlisle and San Mateo" is anchored at the midpoint, and
    the camera it describes sits at one end, 800 m away -- an anchor-only test
    calls that a different camera and draws Gibson twice.
    """
    kept, dropped = [], 0
    for corridor in community:
        covered = any(
            distance_m(corridor.point, vertex) <= DUPLICATE_RADIUS_M
            for other in official
            for line in other.lines
            for vertex in line
        )
        if covered:
            dropped += 1
            continue
        kept.append(corridor)
    return kept, dropped


def build_all() -> dict[str, Any]:
    """Run every source. Returns the assembled payload."""
    from . import albuquerque, osm_cameras, schools  # imported late: each does network I/O

    santa_fe, spec = build_santa_fe()
    abq, unresolved = albuquerque.build()

    # The city boxes overlap along Coors and the Bypass, so a camera there is
    # returned for both cities. Deduplicating the community layer against
    # itself first stops one camera being drawn as two corridors.
    community: list[Corridor] = []
    for city in ("Rio Rancho", "Albuquerque"):
        found = osm_cameras.build(city)
        found, _ = deduplicate(community, found)
        community.extend(found)
    community, duplicates = deduplicate(santa_fe + abq, community)

    corridors = santa_fe + abq + community
    school_points = schools.fetch()
    flagged = schools.flag_corridors(corridors, school_points)

    log.info(
        "%d corridors (%d Santa Fe, %d Albuquerque, %d community after %d duplicates), "
        "%d schools, %d corridors run past a school",
        len(corridors), len(santa_fe), len(abq), len(community), duplicates, len(school_points), flagged,
    )

    return {
        "corridors": corridors,
        "schools": school_points,
        "spec": spec,
        "unresolved": unresolved,
        "counts": {
            "santa_fe": len(santa_fe),
            "albuquerque": len(abq),
            "community": len(community),
            "duplicates_dropped": duplicates,
            "schools": len(school_points),
            "corridors_near_a_school": flagged,
        },
    }


def write(payload: dict[str, Any]) -> None:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    features = []
    for corridor in payload["corridors"]:
        feature = corridor.as_feature()
        feature["properties"]["schools_nearby"] = getattr(corridor, "schools_nearby", [])
        features.append(feature)
    (SITE_DATA_DIR / "corridors.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"), default=_json_default)
    )

    (SITE_DATA_DIR / "schools.geojson").write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": [s.as_feature() for s in payload["schools"]]},
            separators=(",", ":"),
            default=_json_default,
        )
    )

    santa_fe_spec = payload["spec"]
    rio_rancho = yaml.safe_load((DATA_DIR / "jurisdictions.yaml").read_text())
    (SITE_DATA_DIR / "meta.json").write_text(
        json.dumps(
            {
                "built": date.today().isoformat(),
                "counts": payload["counts"],
                "school_proximity_m": SCHOOL_PROXIMITY_M,
                "unresolved": payload["unresolved"],
                "jurisdictions": rio_rancho["jurisdictions"],
                "santa_fe": {
                    "program": santa_fe_spec["program"],
                    "penalties": santa_fe_spec["penalties"],
                },
            },
            indent=1,
            default=_json_default,
        )
    )
    log.info("wrote %s", SITE_DATA_DIR)
