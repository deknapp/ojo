# Where every number came from, and what turned out to be useless

The point of writing this down is that the map makes claims about where you
can be fined, and a claim like that is worth exactly as much as its source.

## The legal position, which is the surprising part

Santa Fe's program is the **Santa Fe Traffic Operations Program**, "STOP",
SFCC 1987 §24-4, created by [Ordinance 2008-47][ord2008] and amended by
[Bill 2025-6][bill] to add noise cameras.

**There is no duty to publish camera locations.** §24-4.6(A) requires only
that the city "install advance signal warnings as required by Section
66-7-103.1 NMSA 1978" — and [that statute][103] is about rumble strips and
warning beacons at photo-enforced *traffic signals*, i.e. red-light cameras.
It says nothing about mobile speed trailers.

So the posted signs and the Facebook announcements are police policy, not a
legal obligation, and they can stop at any time. That single fact is why this
repository has a hand-curated YAML file in it instead of a scraper.

Two other things in the ordinance matter:

- **§24-4.5(H)** sets the thresholds and fines. You are cited above 10 mph
  over, or above 5 mph over in a school or construction zone, at $50/$100
  first offense and $100/$150 on a repeat within two years. Vehicle noise is
  $500. This is the most useful information in the whole project and it is not
  in any news article.
- **§24-4.6(E)** requires SFPD to give the Public Safety Committee a *monthly
  report* including violation statistics. If those packets are posted, they
  are a recurring official record. As of September 2026 the city's committee
  minutes archive stops at January 2026, so this has not been usable yet.

## Sources that work

**City of Albuquerque, [automated speed enforcement][abq].** Static
server-rendered HTML, a bulleted list of 40 entries of the form
`Gibson between Carlisle and San Mateo (eastbound), live 4/25/2022.` Activation
dates run from 2022 to September 2026, so it is actively maintained. This is
the only official, current, city-published enforcement list in New Mexico, and
39 of its 40 entries resolve to geometry here.

**Santa Fe New Mexican.** Block-level locations for five of the six Santa Fe
units, plus the launch date and grace period. Reporting rather than a feed, so
each entry carries the retrieval date.

**OpenStreetMap.** Road geometry, speed limits where tagged, and Rio Rancho's
cameras — sixteen of them mapped in a December 2025 survey, with street,
direction and posted limit on each node. One Albuquerque node added in August
2026 even carries a `check_date` and a link back to the city's own page, which
is the verification discipline this project tries to imitate.

**NCES public-school locations.** 308 schools in the study area. Note the trap:
there is a layer on ArcGIS called "New Mexico Public Schools" that holds 43
features, *all in Santa Fe*, despite the statewide name. The NCES national
layer is the right one.

## Sources that do not work

**SFPD's Facebook page** is where the city says it will announce locations. It
is login-walled; fetching it returns a cookie and login gate, no post content.
It cannot be read programmatically, and working around that gate would be both
brittle and a bad idea.

**photoenforced.com** is anonymously crowdsourced with no API and almost
nothing for New Mexico.

**speedcams.us** is derived from OpenStreetMap, which is why it showed exactly
one Santa Fe pin — an artefact of OSM's gap, not a finding about Santa Fe.

**NMDOT's NMRoads CCTV feed** (`servicev5.nmroads.com/RealMapWAR/GetCameraInfo`)
is real, open, and returns 183 cameras statewide with coordinates and live
snapshots. It is deliberately **not** in this project. Those are road-condition
cameras; they do not issue citations. Drawing them next to enforcement
corridors would undermine the one thing a highlighted road here is supposed to
mean.

**A public records request** would probably produce Santa Fe's deployment log
under IPRA, and was considered and dropped: weeks of waiting for something the
published sources approximate today.

## Two mistakes worth recording

**Overpass.** An early check used a mirror that answered every query with an
empty result — including a control query for traffic signals in central Santa
Fe, which cannot be zero. It briefly looked as though OpenStreetMap had no
camera data in New Mexico at all. It has 66 nodes. Every Overpass query in
this repository is now issued against the main endpoint, and the lesson is
that a query returning nothing should be tested against something that must
return something.

**Nominatim.** Geocoding `7500 Airport Road, Santa Fe` returns a point on *Old
Airport Road*, a different street. Every location in this project is therefore
snapped onto a way whose name really is the announced street; that snap moves
the Airport Road corridor 101 m onto the correct road. Similar traps: the city
writes "Montano" and OSM stores "Montaño", the city writes "St. Joseph" and OSM
stores "Saint Joseph's Drive Northwest".

## One cross-check that came out well

The Albuquerque junctions are computed from road geometry — where two named
ways share a vertex. Those computed junctions land within about 10 m of the
speed-camera nodes that OpenStreetMap volunteers independently mapped at the
same intersections. Two unrelated methods agreeing is the best evidence
available here that the geometry is right.

[ord2008]: https://santafenm.gov/archive_center/document/441
[bill]: https://santafenm.gov/Sound_Cameras_Placed_in_Section_24-4_STOP_Program_(Bill).pdf
[103]: https://law.justia.com/codes/new-mexico/2018/chapter-66/article-7/section-66-7-103.1/
[abq]: https://www.cabq.gov/automated-speed-enforcement
