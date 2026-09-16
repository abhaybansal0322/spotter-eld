"""Shared fixtures and canned OpenRouteService payloads, trimmed to the fields the code reads.

Coordinates are Denver to Cheyenne. Every longitude is below -100, so a latitude that was never swapped
out of ORS's [lng, lat] order is out of range and cannot pass for a real one.
"""
import pytest
from rest_framework.test import APIClient

from trips.services import geocode

ORS_TEST_KEY = "test-ors-key"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def ors(settings):
    """A configured ORS key and cold geocode caches, for any test that reaches the network layer."""
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
