"""Shared fixtures and canned OpenRouteService payloads, trimmed to the fields the code reads.

Coordinates are Denver to Cheyenne. Every longitude is below -100, so a latitude that was never swapped
out of ORS's [lng, lat] order is out of range and cannot pass for a real one.
"""
import math

import pytest
from rest_framework.test import APIClient

from trips.services import geocode, http, routing
from trips.services.route_index import EARTH_RADIUS_MI

ORS_TEST_KEY = "test-ors-key"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def ors(settings, db):
    """A configured ORS key and cold geocode caches, for any test that reaches the network layer.

    The persistent geocode cache is a table, so these tests get the (per-test, rolled back) database too."""
    settings.ORS_API_KEY = ORS_TEST_KEY
    geocode.clear_caches()
    yield
    geocode.clear_caches()


def pelias_feature(lng, lat, **properties):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lng, lat]}, "properties": properties}


@pytest.fixture
def pelias_search_denver():
    """ORS /geocode/search?text=denver, co&size=1."""
    return {
        "type": "FeatureCollection",
        "features": [
            pelias_feature(
                -104.9903, 39.7392,
                label="Denver, CO, USA", locality="Denver", county="Denver County",
                region="Colorado", region_a="CO", country_a="USA",
            ),
        ],
    }


@pytest.fixture
def pelias_reverse_cheyenne():
    """ORS /geocode/reverse?point.lat=41.14&point.lon=-104.82&size=1."""
    return {
        "type": "FeatureCollection",
        "features": [
            pelias_feature(
                -104.8202, 41.1400,
                label="1 Capitol Ave, Cheyenne, WY, USA", locality="Cheyenne", county="Laramie County",
                region="Wyoming", region_a="WY", country_a="USA",
            ),
        ],
    }


@pytest.fixture
def pelias_empty():
    return {"type": "FeatureCollection", "features": []}


@pytest.fixture
def ors_directions_denver_to_cheyenne():
    """ORS POST /v2/directions/driving-hgv/geojson with units=mi, three input points, two segments.

    Step names include an unnamed ramp ("") and ORS's arrival placeholder ("-"), both of which must be dropped.
    Step distances sum to the summary distance, 101.3 miles.
    """
    return {
        "type": "FeatureCollection",
        "bbox": [-104.9903, 39.7392, -104.8202, 41.14],
        "features": [
            {
                "type": "Feature",
                "bbox": [-104.9903, 39.7392, -104.8202, 41.14],
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-104.9903, 39.7392], [-104.987, 39.88], [-104.9, 40.5], [-104.8202, 41.14]],
                },
                "properties": {
                    "summary": {"distance": 101.3, "duration": 6120.0},
                    "segments": [
                        {
                            "distance": 41.0,
                            "steps": [
                                {"distance": 0.5, "name": "Broadway", "type": 11, "way_points": [0, 1]},
                                {"distance": 0.3, "name": "", "type": 12, "way_points": [1, 1]},
                                {"distance": 40.2, "name": "I-25 N", "type": 6, "way_points": [1, 2]},
                                {"distance": 0.0, "name": "-", "type": 10, "way_points": [2, 2]},
                            ],
                        },
                        {
                            "distance": 60.3,
                            "steps": [
                                {"distance": 60.3, "name": "I-25 N", "type": 11, "way_points": [2, 3]},
                                {"distance": 0.0, "name": "-", "type": 10, "way_points": [3, 3]},
                            ],
                        },
                    ],
                    "way_points": [0, 2, 3],
                },
            },
        ],
        "metadata": {"query": {"profile": "driving-hgv", "units": "mi"}},
    }


# Synthetic trips for planner and API tests: routes run due north from a base point, where miles map exactly to latitude.

BASE_LAT, BASE_LNG = 35.0, -101.0
DEGREES_PER_MILE = 180 / (math.pi * EARTH_RADIUS_MI)


def north_of_base(miles, lng=BASE_LNG):
    return (BASE_LAT + miles * DEGREES_PER_MILE, lng)


def pelias_place(lng, lat, locality, state):
    return {"features": [pelias_feature(lng, lat, locality=locality, region_a=state)]}


def directions_payload(geometry, legs):
    """ORS geojson directions payload. geometry is (lat, lng); legs is one list of (distance, road) steps per leg."""
    coordinates = [[lng, lat] for lat, lng in geometry]
    lats, lngs = [lat for lat, _ in geometry], [lng for _, lng in geometry]
    segments = [
        {"distance": round(sum(distance for distance, _ in steps), 1),
         "steps": [{"distance": distance, "name": name} for distance, name in steps] + [{"distance": 0.0, "name": "-"}]}
        for steps in legs
    ]
    return {"features": [{
        "bbox": [min(lngs), min(lats), max(lngs), max(lats)],
        "geometry": {"coordinates": coordinates},
        "properties": {"summary": {"distance": round(sum(s["distance"] for s in segments), 1)}, "segments": segments},
    }]}


def straight_trip(pickup_mile, dropoff_mile, road="US-287 N", legs=2):
    """A due-north route. legs=1 is the two-point route used when the trip starts at the pickup."""
    geometry = [north_of_base(mile) for mile in range(0, int(dropoff_mile) + 1, 10)]
    steps = [[(dropoff_mile, road)]] if legs == 1 else [[(pickup_mile, road)], [(dropoff_mile - pickup_mile, road)]]
    return directions_payload(geometry, steps)


class FakeOrs:
    """Stands in for http.request_json and answers ORS by URL.

    addresses maps normalized search text to a payload. reverse(lat, lng, radius_km) returns a locality name, or
    None for a miss. directions is a payload, or an exception to raise from the routing call.
    """

    def __init__(self, directions, addresses, reverse=None):
        self.directions = directions
        self.addresses = addresses
        self.reverse = reverse or (lambda lat, lng, radius: f"Town {lat:.2f}")
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((url, kwargs))
        params = kwargs.get("params", {})
        if url == geocode.SEARCH_URL:
            return self.addresses.get(params["text"], {"features": []})
        if url == geocode.REVERSE_URL:
            name = self.reverse(params["point.lat"], params["point.lon"], params["boundary.circle.radius"])
            return pelias_place(params["point.lon"], params["point.lat"], name, "XX") if name else {"features": []}
        if url == routing.DIRECTIONS_URL:
            if isinstance(self.directions, Exception):
                raise self.directions
            return self.directions
        raise AssertionError(f"unexpected call to {url}")

    def requests(self, url):
        return [kwargs for called, kwargs in self.calls if called == url]

    def urls(self, url):
        return [kwargs.get("params", {}) for kwargs in self.requests(url)]


@pytest.fixture
def fake_ors(ors, monkeypatch):
    """Factory installing a FakeOrs with three known addresses: "Origin, AA", "Pickup, BB" and "Dropoff, CC"."""

    def install(directions, reverse=None):
        addresses = {
            "origin, aa": pelias_place(BASE_LNG, BASE_LAT, "Origin", "AA"),
            "pickup, bb": pelias_place(BASE_LNG, BASE_LAT + 1, "Pickup", "BB"),
            "dropoff, cc": pelias_place(BASE_LNG, BASE_LAT + 2, "Dropoff", "CC"),
        }
        fake = FakeOrs(directions, addresses, reverse)
        monkeypatch.setattr(http, "request_json", fake)
        return fake

    return install
