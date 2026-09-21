# ojo

[![tests](https://github.com/deknapp/ojo/actions/workflows/tests.yml/badge.svg)](https://github.com/deknapp/ojo/actions/workflows/tests.yml)

Where automated speed and noise enforcement is in northern and central New
Mexico — Santa Fe, Albuquerque, Rio Rancho — what actually triggers a citation
there, and how confident any of it is.

**Live map: https://deknapp.github.io/ojo/**

Named for the Spanish for *eye*, and for Ojo Caliente up the road.

> Santa Fe's cameras went live on 1 September 2026. Warnings end and citations
> start on **1 October 2026**.

## Why this exists

Santa Fe bought six relocatable enforcement trailers and announces where they
are on a Facebook page. Albuquerque bolted forty cameras to poles and publishes
a list with activation dates. Rio Rancho publishes nothing, and everything
known about its sixteen cameras was mapped by volunteers.

Three cities, one state, three completely different levels of legibility. This
project renders all three on one map and is explicit about which is which,
because the difference between "the city published this" and "somebody drove
past it in December" is the whole story.

## What it tells you that nothing else does

**The number that actually matters.** Under the Santa Fe ordinance you are not
cited at the speed limit. You are cited at more than **10 mph over** — or more
than **5 mph over** in a school or construction zone, where the fine also
doubles. So the map shows a *threshold speed* per corridor, not a limit:

| Where | Cited above | First offense | Again within 2 years |
|---|---|---|---|
| Anywhere else | 10 mph over | $50 | $100 |
| School or construction zone | 5 mph over | $100 | $150 |
| Vehicle noise | over the posted limit | $500 | — |

Those figures are from [the ordinance itself][bill] (SFCC 24-4.5(H)), not from
press coverage.

**Where the threshold halves.** School zones are the highest-risk category per
mile and OpenStreetMap has *zero* school-zone objects in Santa Fe, so schools
come from the NCES public-school universe and every corridor running past one
is flagged. The flag says "school nearby — watch for a posted zone", never
"this is a zone": under [NMSA 1978 66-7-301][statute] the 15 mph limit needs
children present *and* the zone properly posted, and signs are in no dataset.

**How stale the claim is.** Every corridor carries the date it was last
confirmed and the source it came from, on the map and in the route results. A
Santa Fe trailer confirmed in August is a weaker claim than an Albuquerque pole
the city listed last week, and the page says so rather than drawing them alike.

## Corridors, not pins

The Santa Fe units are trailers. They get towed. A pin asserts *the camera is
here*, which stops being true the moment one moves, and a driver who learns to
relax between pins has been taught the wrong lesson by the map. The city
announces a block and signs a zone, so the map draws the zone.

## Typing an address

The route box suggests addresses as you type. Those come from [Photon][photon],
bounded to northern and central New Mexico, because OpenStreetMap's Nominatim
asks people not to send it a request per keystroke and it is right to ask. A
suggestion carries its own coordinates, so picking one plans the route with no
geocoding request at all; an address typed straight through and never picked
goes to Nominatim on submit, one request a second. Routing is
[OSRM][osrm]. All three run in the browser against public services — this page
has no backend, so there is nowhere for a route or an address to be logged.

The suggestions are also the fix for the quiet failure that came before them:
four different places share 1050 Old Pecos Trail, and a lookup that silently
took the first one would put your route somewhere you did not ask for.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

ojo build     # refresh every source, write site/data/
ojo serve     # serve site/ at http://127.0.0.1:8000
```

The first `ojo build` downloads the 134 MB Geofabrik extract of New Mexico into
`.cache/` and every later build reads it locally — the whole state parses in
about three and a half seconds. Remote responses are cached alongside it, so a
rebuild is cheap and the exact bytes behind a claim are still on disk when
someone asks. [docs/sourcing.md](docs/sourcing.md) explains why this reads a
file rather than calling the Overpass API.

## Where the data comes from

| Source | What it gives | How good it is |
|---|---|---|
| [City of Albuquerque][abq] | 40 locations, direction, activation date | Official, current, kept up to date |
| [Santa Fe New Mexican][sfnm] | Santa Fe's 5 block-level locations | Reporting; dated, not a feed |
| [Ordinance / Bill 2025-6][bill] | Thresholds, fines, program rules | The law itself |
| [OpenStreetMap][osm] (Geofabrik extract) | Road geometry, speed limits, Rio Rancho cameras | Community; ages unevenly |
| [NCES][nces] | 308 school locations | Federal, authoritative for location only |

Full reasoning, including the sources that turned out to be useless and why, is
in [docs/sourcing.md](docs/sourcing.md).

## What this does not know

- **Santa Fe's trailers move**, and no law requires the city to say when. Treat
  every Santa Fe corridor as *last seen*, not *currently there*.
- **Construction zones** carry the same halved threshold as school zones and
  are not mapped here at all.
- **Speed limits** come from OpenStreetMap, which has them on about a fifth of
  Santa Fe's drivable ways. Where the limit is unknown the page says so instead
  of inventing a number.
- **One published Albuquerque location** cannot be matched to a road and is
  printed by `ojo build` rather than silently dropped. A camera this code
  cannot place is not a camera that is not on the road.

## Not affiliated, not advice

This is not connected to any city or police department, and a corridor here is
a claim with a date on it, not a guarantee. The signs by the road are
authoritative. The reliable way not to get a ticket is to drive the limit —
enforcement goes where the crashes are, which is the more useful thing this map
has to say.

[abq]: https://www.cabq.gov/automated-speed-enforcement
[sfnm]: https://www.santafenewmexican.com/news/local_news/santa-fe-speed-cameras-to-launch-monday/article_c67f0db4-aa74-4ad4-b168-987cba2af4e1.html
[bill]: https://santafenm.gov/Sound_Cameras_Placed_in_Section_24-4_STOP_Program_(Bill).pdf
[statute]: https://law.justia.com/codes/new-mexico/2018/chapter-66/article-7/section-66-7-301/
[photon]: https://photon.komoot.io/
[osrm]: https://project-osrm.org/
[osm]: https://www.openstreetmap.org/
[nces]: https://data-nces.opendata.arcgis.com/
