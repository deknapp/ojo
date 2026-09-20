import math

from ojo.geometry import distance_m, snap_to_lines, walk_along


def test_distance_known_separation():
    # One degree of latitude is about 111 km anywhere.
    assert 110_000 < distance_m((35.0, -106.0), (36.0, -106.0)) < 112_000


def test_distance_shrinks_with_longitude_at_latitude():
    east = distance_m((35.0, -106.0), (35.0, -105.0))
    north = distance_m((35.0, -106.0), (36.0, -106.0))
    assert east < north
    assert math.isclose(east / north, math.cos(math.radians(35.0)), rel_tol=0.01)


def test_snap_picks_the_nearer_line():
    near = [(35.0, -106.0), (35.0, -105.99)]
    far = [(35.1, -106.0), (35.1, -105.99)]
    point, distance, index = snap_to_lines((35.0005, -105.995), [far, near])
    assert index == 1
    assert distance < 100
    assert abs(point[0] - 35.0) < 1e-6


def test_walk_along_trims_to_radius():
    line = [(35.0, -106.0 + 0.001 * i) for i in range(20)]
    runs = walk_along([line], (35.0, -106.0), 100.0)
    assert runs
    assert all(distance_m(p, (35.0, -106.0)) <= 100.0 for run in runs for p in run)
