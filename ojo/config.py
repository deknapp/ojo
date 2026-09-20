"""Study area, endpoints, and the constants that encode a judgement call.

Anything here that is a guess rather than a fact says so, because the whole
point of this project is that a driver can tell the difference.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"
CACHE_DIR = ROOT / ".cache"

#: Santa Fe, Albuquerque and Rio Rancho, plus the I-25 corridor between them.
#: Automated enforcement in New Mexico is a city-by-city affair; there is none
#: on the state highways north of Santa Fe, so the box stops there.
BBOX = (34.95, -107.00, 35.95, -105.70)  # south, west, north, east

#: Per-city boxes. Overpass charges for area, and a case-insensitive regex on
#: `name` across the whole study box times out or gets rate-limited -- so every
#: street lookup is asked inside the city that actually announced the camera.
CITY_BBOX = {
    "Santa Fe": (35.57, -106.12, 35.76, -105.86),
    "Albuquerque": (34.95, -106.85, 35.28, -106.45),
    "Rio Rancho": (35.19, -106.80, 35.36, -106.55),
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

#: Both services are volunteer-funded and ask to be identified. Anything
#: hammering them anonymously deserves the block it will get.
USER_AGENT = "ojo/0.1 (+https://github.com/deknapp/ojo)"

#: Nominatim's usage policy is one request per second. This is deliberately
#: slower than required.
NOMINATIM_DELAY_S = 1.2

#: Half-length of a drawn enforcement corridor, in metres.
#:
#: This is the most important guess in the project and it is not derived from
#: anything. Santa Fe's units are trailers that move, and the city publishes a
#: block, not a point. A block in this part of town runs roughly 200-400 m, and
#: a speed measurement is taken over a stretch rather than at a line, so the
#: drawn corridor is 300 m either side of the announced location.
#:
#: It is drawn as a corridor rather than a pin for a reason: a pin says "the
#: camera is HERE", which is false the moment the trailer is towed thirty
#: metres, and a driver who learns to relax between pins has been taught the
#: wrong lesson by the map.
CORRIDOR_HALF_LENGTH_M = 300.0

#: Fixed-pole cameras (Albuquerque, Rio Rancho) do not move, so their corridor
#: is tighter -- but a camera still measures over a distance and the published
#: location is "Gibson between Carlisle and San Mateo", not a coordinate.
FIXED_CORRIDOR_HALF_LENGTH_M = 150.0

#: NMSA 1978 66-7-301 caps speed at 15 mph "when passing a school while
#: children are going to or leaving school and when the school zone is properly
#: posted" -- three conditions, all of which have to hold. The distance below is
#: how far from a school this tool will flag a road as *possibly* school-zoned.
#:
#: It is a proximity heuristic, not the legal zone. The legal zone is whatever
#: the signs say, and the signs are not in any dataset. The site labels these
#: as "school nearby -- check for a posted zone", never as a zone boundary.
SCHOOL_PROXIMITY_M = 300.0

#: NCES public-school universe, published by the National Center for Education
#: Statistics. Authoritative for where schools are; says nothing at all about
#: where zones are signed.
#:
#: There is a "New Mexico Public Schools" layer on ArcGIS that looks like the
#: obvious choice and is not: it holds 43 features, all of them in Santa Fe,
#: despite the statewide name. This one has 312 inside the study area.
SCHOOLS_FEATURE_SERVICE = (
    "https://services1.arcgis.com/Ua5sjt3LWTPigjyD/arcgis/rest/services/"
    "Public_School_Locations_Current/FeatureServer/0/query"
)

#: Albuquerque publishes its own list. This is the only official, current,
#: machine-readable-ish source of enforcement locations in the state.
ABQ_LIST_URL = "https://www.cabq.gov/automated-speed-enforcement"

#: Public OSRM. Fine for a demo and explicitly not for production traffic; the
#: site degrades to "no route" rather than failing loudly if it is unavailable.
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
