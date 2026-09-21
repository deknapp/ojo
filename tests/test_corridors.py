from ojo.corridors import normalise_street, parse_maxspeed


def test_leading_compass_word_is_not_part_of_the_name():
    assert normalise_street("West Zia Road") == "zia road"
    assert normalise_street("East Zia Road") == "zia road"
    assert normalise_street("Zia Road") == "zia road"


def test_a_qualifier_that_is_not_a_compass_word_makes_a_different_street():
    # Santa Fe has both, they run close together, and putting an enforcement
    # corridor on the wrong one is the failure this project exists to avoid.
    assert normalise_street("Old Airport Road") != normalise_street("Airport Road")


def test_maxspeed_parsing():
    assert parse_maxspeed("35 mph") == 35
    assert parse_maxspeed("30") == 30
    assert parse_maxspeed(None) is None
    assert parse_maxspeed("walk") is None
    assert parse_maxspeed("") is None
