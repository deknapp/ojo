"""The parser is the part most likely to break silently when the city edits a
sentence, so every grammar the published list actually uses is pinned here."""

import pytest

from ojo.albuquerque import (
    matches_street,
    normalise_abq,
    parse,
    parse_date,
    strip_accents,
)

PUBLISHED = [
    "Gibson between Carlisle and San Mateo (eastbound), live 4/25/2022.",
    "Unser at Tower (northbound), live 6/10/2022.",
    "San Mateo just north of Montgomery (southbound), live 8/01/2022.",
    "Montgomery and Jennifer (westbound), live 3/13/2023.",
    "Paseo del Norte west of Louisiana (westbound), live 12/05/2023.",
    "Central between Louisiana and San Pedro (westbound), live 10/3/25.",
    "Coors north of St. Joseph (southbound), 7/29/2026.",
    "Unser at Flor Del Sol just north of Dellyne (northbound), live 8/01/2022.",
    "Wyoming and just north of Academy (northbound), live 5/23/2023.",
]


def test_every_published_grammar_parses():
    parsed, unparsed = parse(PUBLISHED)
    assert unparsed == []
    assert len(parsed) == len(PUBLISHED)


def test_between_yields_two_cross_streets():
    parsed, _ = parse([PUBLISHED[0]])
    assert parsed[0].street == "Gibson"
    assert parsed[0].cross == ["Carlisle", "San Mateo"]
    assert parsed[0].direction == "eastbound"
    assert parsed[0].live == "2022-04-25"


def test_two_digit_year_is_expanded():
    assert parse_date("10/3/25") == "2025-10-03"
    assert parse_date("7/29/2026") == "2026-07-29"


def test_a_second_relation_is_dropped_from_the_cross_street():
    # "Flor Del Sol just north of Dellyne" names the junction twice; only the
    # first cross street locates it.
    parsed, _ = parse(["Unser at Flor Del Sol just north of Dellyne (northbound), live 8/01/2022."])
    assert parsed[0].cross == ["Flor Del Sol"]


def test_a_leading_relation_is_dropped_from_the_cross_street():
    # "and just north of Academy" puts the relation after the connector.
    parsed, _ = parse(["Wyoming and just north of Academy (northbound), live 5/23/2023."])
    assert parsed[0].cross == ["Academy"]


@pytest.mark.parametrize(
    "osm,announced,expected",
    [
        ("Gibson Boulevard Southeast", "Gibson", True),
        ("Gibson Boulevard", "Gibson", True),
        ("Gibson", "Gibson", True),
        # Two different Albuquerque roads, both with cameras on them.
        ("Coors Boulevard Bypass Northwest", "Coors", False),
        ("Coors Boulevard Northwest", "Coors Bypass", False),
        # The city drops accents; OpenStreetMap keeps them.
        ("Avenida César Chávez Southeast", "Avenida Cesar Chavez", True),
        ("Montaño Road Northwest", "Montano Road", True),
        ("Saint Joseph's Drive Northwest", "Saint Josephs Drive", True),
        # A different street that merely starts the same way.
        ("Gibson Court Northeast", "Gibson Boulevard", False),
    ],
)
def test_street_matching(osm, announced, expected):
    assert matches_street(osm, announced) is expected


def test_accents_and_quadrants_normalise_away():
    assert strip_accents("Montaño") == "Montano"
    assert normalise_abq("Gibson Boulevard Southeast") == "gibson boulevard"
