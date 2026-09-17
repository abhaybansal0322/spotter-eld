"""RouteIndex mile-to-coordinate tests over hand-built polylines."""
import math

import pytest

from trips.services import route_index
from trips.services.route_index import EARTH_RADIUS_MI, RouteIndex, road_at, simplify

# Along a meridian, haversine distance is exactly proportional to latitude, so expected points are exact.
DEGREES_PER_MILE = 180 / (math.pi * EARTH_RADIUS_MI)


def _north(miles, lng=-77.0):
    return (miles * DEGREES_PER_MILE, lng)


def _close(actual, expected, tolerance=1e-9):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def test_two_point_geometry_endpoints_and_midpoint():
    start, end = (37.5407, -77.4360), (39.2904, -76.6122)  # Richmond, Baltimore
    index = RouteIndex([start, end], total_miles=150)

    assert index.coordinate_at(0) == start
    assert index.coordinate_at(150) == end
    assert _close(index.coordinate_at(75), ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2))


def test_uneven_segments_interpolate_into_the_right_leg():
    index = RouteIndex([_north(0), _north(10), _north(40), _north(100)], total_miles=100)

    assert _close(index.coordinate_at(5), _north(5))
    assert _close(index.coordinate_at(10), _north(10))
    assert _close(index.coordinate_at(25), _north(25))
    assert _close(index.coordinate_at(70), _north(70))


def test_coordinate_at_clamps_to_the_route():
    first, last = _north(0), _north(50)
    index = RouteIndex([first, _north(20), last], total_miles=50)

    assert index.coordinate_at(-10) == first
    assert index.coordinate_at(50.001) == last
    assert index.coordinate_at(10_000) == last


def test_road_distance_scales_the_polyline():
    geometry = [_north(0), _north(30), _north(90)]
    assert sum(route_index._haversine_mi(a, b) for a, b in zip(geometry, geometry[1:])) == pytest.approx(90)

    index = RouteIndex(geometry, total_miles=100)

    assert _close(index.coordinate_at(50), _north(45))
    assert index.coordinate_at(100) == geometry[-1]


def test_road_at_is_containment_not_nearest():
    steps = [(0.0, "Broadway"), (0.8, "I-25 N"), (350.8, "US-87 N")]

    assert road_at(0.0, steps) == "Broadway"
    assert road_at(0.5, steps) == "Broadway"
    assert road_at(0.8, steps) == "I-25 N"  # a step owns its own starting mile
    assert road_at(250.8, steps) == "I-25 N"  # 250 miles into a 350-mile step is still on that road
    assert road_at(350.8, steps) == "US-87 N"
    assert road_at(10_000, steps) == "US-87 N"


def test_road_at_inside_an_unnamed_step_is_none():
    # Live LA to Boston: a short named Thruway step, then an unnamed 159.5-mile step carrying the stop at mile 2962.
    steps = [(2828.1, "New York State Thruway"), (2842.7, None), (3002.2, "Boston Road")]

    assert road_at(2830.0, steps) == "New York State Thruway"
    assert road_at(2961.8, steps) is None


def test_road_at_before_the_first_step_or_without_steps():
    assert road_at(4.9, [(5.0, "I-80 W")]) is None
    assert road_at(-1, [(0.0, "Broadway")]) is None
    assert road_at(60, []) is None


@pytest.mark.parametrize(
    ("geometry", "total_miles"),
    [
        ([(37.5, -77.4)], 0),
        ([(37.5, -77.4)], 12),
        ([(37.5, -77.4), (37.5, -77.4)], 0),
        ([(37.5, -77.4), (37.5, -77.4)], 12),
    ],
    ids=["single-vertex", "single-vertex-with-length", "identical-pair", "identical-pair-with-length"],
)
def test_degenerate_geometry_does_not_divide_by_zero(geometry, total_miles):
    index = RouteIndex(geometry, total_miles)

    for mile in (-1, 0, 6, 12, 100):
        assert index.coordinate_at(mile) == geometry[0]


def test_duplicate_vertices_inside_a_route_interpolate_cleanly():
    index = RouteIndex([_north(0), _north(10), _north(10), _north(20)], total_miles=20)

    assert _close(index.coordinate_at(10), _north(10))
    assert _close(index.coordinate_at(15), _north(15))


def test_empty_geometry_is_rejected():
    with pytest.raises(ValueError):
        RouteIndex([], total_miles=0)


class _CountingList(list):
    """A list that counts element reads, so a linear scan cannot hide inside bisect or a loop."""

    reads = 0

    def __getitem__(self, item):
        type(self).reads += 1
        return super().__getitem__(item)


def test_lookups_are_logarithmic_and_distances_are_built_once(monkeypatch):
    vertices = 10_000
    geometry = [_north(mile) for mile in range(vertices)]
    haversine_calls = 0
    real_haversine = route_index._haversine_mi

    def counting_haversine(a, b):
        nonlocal haversine_calls
        haversine_calls += 1
        return real_haversine(a, b)

    monkeypatch.setattr(route_index, "_haversine_mi", counting_haversine)
    index = RouteIndex(geometry, total_miles=vertices - 1)
    assert haversine_calls == vertices - 1

    index._miles = _CountingList(index._miles)
    _CountingList.reads = 0
    queries = 1_000
    for query in range(queries):
        index.coordinate_at(query * 9.999)

    assert haversine_calls == vertices - 1  # nothing recomputed per query
    # bisect over 10,000 entries reads about 14 elements, plus a few for interpolation. A linear scan would
    # read thousands per call; this bound allows 20 per call and fails by orders of magnitude on a scan.
    assert _CountingList.reads <= queries * 20
    assert _close(index.coordinate_at(4321.5), _north(4321.5), tolerance=1e-6)


def test_simplify_collapses_a_straight_line_to_its_ends():
    line = [(35.0 + step * 0.01, -101.0 + step * 0.02) for step in range(100)]

    assert simplify(line, 0.0001) == [line[0], line[-1]]


def test_simplify_keeps_a_sharp_corner():
    out_and_back = [(35.0 + step * 0.01, -101.0) for step in range(50)] + [(35.49, -101.0 + step * 0.01) for step in range(1, 50)]

    simplified = simplify(out_and_back, 0.0001)

    assert simplified == [out_and_back[0], (35.49, -101.0), out_and_back[-1]]


def test_simplify_returns_an_ordered_subset_with_both_ends():
    import random

    rng = random.Random(7)
    walk = [(35.0, -101.0)]
    for _ in range(2_000):
        lat, lng = walk[-1]
        walk.append((lat + rng.uniform(-0.01, 0.01), lng + rng.uniform(-0.01, 0.01)))

    simplified = simplify(walk, 0.005)

    assert simplified[0] == walk[0] and simplified[-1] == walk[-1]
    positions = [walk.index(point) for point in simplified]
    assert positions == sorted(positions)
    assert 2 < len(simplified) < len(walk)


@pytest.mark.parametrize("points", [[], [(1.0, 2.0)], [(1.0, 2.0), (3.0, 4.0)]], ids=["empty", "one", "two"])
def test_simplify_short_inputs_are_unchanged(points):
    assert simplify(points, 0.0001) == points


def test_simplify_handles_fifty_thousand_points_without_recursion():
    import random
    import sys

    # A long noisy highway: tens of thousands of vertices, many of them significant at this tolerance.
    rng = random.Random(1)
    road, lat, lng = [], 35.0, -101.0
    for _ in range(50_000):
        lat += 0.0002 + rng.uniform(-0.00005, 0.00005)
        lng += rng.uniform(-0.0002, 0.0002)
        road.append((lat, lng))
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(200)  # a recursive implementation would need far more than this
    try:
        simplified = simplify(road, 0.0001)
    finally:
        sys.setrecursionlimit(limit)

    assert simplified[0] == road[0] and simplified[-1] == road[-1]
    assert len(simplified) > 1_000
