from ojo.corridors import Corridor
from ojo.export import deduplicate


def _corridor(id_, lat, lon, jurisdiction="Albuquerque"):
    return Corridor(
        id=id_, label=id_, jurisdiction=jurisdiction, street="Somewhere", status="active",
        enforcement=["speed"], point=(lat, lon), lines=[[(lat, lon), (lat, lon + 0.001)]],
        maxspeed_mph=40, maxspeed_source="test", last_confirmed="2026-01-01",
    )


def test_a_community_camera_at_an_official_one_is_dropped():
    official = [_corridor("official", 35.0583, -106.6043)]
    community = [_corridor("osm-1", 35.0583, -106.6043, "Albuquerque")]
    kept, dropped = deduplicate(official, community)
    assert dropped == 1
    assert kept == []


def test_a_community_camera_elsewhere_is_kept():
    official = [_corridor("official", 35.0583, -106.6043)]
    community = [_corridor("osm-2", 35.2500, -106.6770, "Rio Rancho")]
    kept, dropped = deduplicate(official, community)
    assert dropped == 0
    assert len(kept) == 1
