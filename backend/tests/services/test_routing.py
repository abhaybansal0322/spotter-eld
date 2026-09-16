"""Routing tests against the real http.request_json, with ORS answered by `responses`."""
import json

import pytest
import responses
from django.core.exceptions import ImproperlyConfigured
from responses import registries

from tests.conftest import ORS_TEST_KEY
from trips.services import http, routing

pytestmark = pytest.mark.usefixtures("ors")

DENVER, LOVELAND, CHEYENNE = (39.7392, -104.9903), (40.5, -104.9), (41.14, -104.8202)


@pytest.fixture(autouse=True)
def no_backoff_sleep(monkeypatch):
    """Keep the real retry policy but skip its backoff sleeps, so retry tests run instantly."""
    monkeypatch.setattr(http.SESSION.get_adapter("https://").max_retries, "backoff_factor", 0)


@responses.activate
def test_route_parses_geometry_distance_and_bbox(ors_directions_denver_to_cheyenne):
    responses.post(routing.DIRECTIONS_URL, json=ors_directions_denver_to_cheyenne)

    result = routing.route([DENVER, LOVELAND, CHEYENNE])

    assert result.geometry == [(39.7392, -104.9903), (39.88, -104.987), (40.5, -104.9), (41.14, -104.8202)]
    assert result.total_miles == 101.3
    assert result.bbox == ((39.7392, -104.9903), (41.14, -104.8202))


@responses.activate
def test_route_swaps_ors_lng_lat_order(ors_directions_denver_to_cheyenne):
    responses.post(routing.DIRECTIONS_URL, json=ors_directions_denver_to_cheyenne)

    result = routing.route([DENVER, CHEYENNE])

    assert all(-90 <= lat <= 90 for lat, _ in result.geometry)  # unswapped latitudes would be about -104
    assert result.geometry[0] == DENVER
    (south, west), (north, east) = result.bbox
    assert south < north and west < east and -90 <= south <= 90


@responses.activate
def test_coordinates_are_sent_to_ors_as_lng_lat(ors_directions_denver_to_cheyenne):
    responses.post(routing.DIRECTIONS_URL, json=ors_directions_denver_to_cheyenne)

    routing.route([DENVER, LOVELAND, CHEYENNE])

    (call,) = responses.calls
    assert json.loads(call.request.body) == {
        "coordinates": [[-104.9903, 39.7392], [-104.9, 40.5], [-104.8202, 41.14]],
        "units": "mi",
    }
    assert call.request.headers["Authorization"] == ORS_TEST_KEY
    assert ORS_TEST_KEY not in call.request.url


@responses.activate
def test_named_points_sorted_with_placeholders_dropped(ors_directions_denver_to_cheyenne):
    responses.post(routing.DIRECTIONS_URL, json=ors_directions_denver_to_cheyenne)

    named = routing.route([DENVER, LOVELAND, CHEYENNE]).named_points

    assert [label for _, label in named] == ["Broadway", "I-25 N", "I-25 N"]
    assert [mile for mile, _ in named] == pytest.approx([0.0, 0.8, 41.0])
    assert [mile for mile, _ in named] == sorted(mile for mile, _ in named)


@responses.activate
def test_empty_features_raise_not_found():
    responses.post(routing.DIRECTIONS_URL, json={"type": "FeatureCollection", "features": []})

    with pytest.raises(http.NotFoundError):
        routing.route([DENVER, CHEYENNE])


@responses.activate
def test_ors_404_unroutable_point_raises_not_found():
    responses.post(
        routing.DIRECTIONS_URL,
        status=404,
        json={"error": {"code": 2010, "message": "Could not find routable point within a radius of 350.0 meters"}},
    )

    with pytest.raises(http.NotFoundError):
        routing.route([DENVER, (0.0, -150.0)])


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "FeatureCollection"},
        {"features": [{"type": "Feature", "properties": {}}]},
        {"features": [{"geometry": {"coordinates": [[-104.99, 39.74]]}, "bbox": [0, 0, 0, 0], "properties": {"segments": []}}]},
        [],
    ],
    ids=["no-features-key", "no-geometry", "no-summary", "not-an-object"],
)
@responses.activate
def test_malformed_payload_raises_upstream_error(payload):
    responses.post(routing.DIRECTIONS_URL, json=payload)

    with pytest.raises(http.UpstreamError):
        routing.route([DENVER, CHEYENNE])


@responses.activate
def test_non_json_body_raises_upstream_error():
    responses.post(routing.DIRECTIONS_URL, body="<html>gateway</html>", content_type="text/html")

    with pytest.raises(http.UpstreamError):
        routing.route([DENVER, CHEYENNE])


@responses.activate(registry=registries.OrderedRegistry)
def test_503_retries_then_succeeds(ors_directions_denver_to_cheyenne):
    responses.post(routing.DIRECTIONS_URL, status=503)
    responses.post(routing.DIRECTIONS_URL, status=503)
    responses.post(routing.DIRECTIONS_URL, json=ors_directions_denver_to_cheyenne)

    result = routing.route([DENVER, CHEYENNE])

    assert result.total_miles == 101.3
    assert len(responses.calls) == 3


@responses.activate(registry=registries.OrderedRegistry)
def test_persistent_500_raises_upstream_error_not_requests_exception():
    for _ in range(5):
        responses.post(routing.DIRECTIONS_URL, status=500)

    with pytest.raises(http.UpstreamError) as raised:
        routing.route([DENVER, CHEYENNE])

    assert raised.value.status == 500
    assert type(raised.value) is http.UpstreamError
    assert len(responses.calls) == 4  # the first attempt plus exactly 3 retries, then give up


def test_missing_api_key_fails_loudly_before_any_call(settings):
    settings.ORS_API_KEY = ""

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        with pytest.raises(ImproperlyConfigured):
            routing.route([DENVER, CHEYENNE])
        assert len(mock.calls) == 0


def test_fewer_than_two_coordinates_raise_before_any_call():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        with pytest.raises(ValueError):
            routing.route([DENVER])
        assert len(mock.calls) == 0
