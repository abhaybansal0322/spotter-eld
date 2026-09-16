"""Geocode tests with the network mocked at the http.request_json seam."""
import pytest

from tests.conftest import ORS_TEST_KEY, pelias_feature
from trips.services import geocode, http

pytestmark = pytest.mark.usefixtures("ors")


@pytest.fixture
def fake_ors(monkeypatch):
    """Replace http.request_json with a recorder that answers from a queue of canned payloads."""

    class FakeOrs:
        def __init__(self):
            self.calls = []
            self.payloads = []

        def __call__(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return self.payloads[min(len(self.calls), len(self.payloads)) - 1]

    fake = FakeOrs()
    monkeypatch.setattr(http, "request_json", fake)
    return fake


def test_forward_returns_lat_lng_and_label(fake_ors, pelias_search_denver):
    fake_ors.payloads = [pelias_search_denver]

    assert geocode.forward("Denver, CO") == (39.7392, -104.9903, "Denver, CO")

    method, url, kwargs = fake_ors.calls[0]
    assert (method, url) == ("GET", geocode.SEARCH_URL)
    assert kwargs["params"] == {"text": "denver, co", "size": 1, "boundary.country": "US"}
    assert kwargs["headers"] == {"Authorization": ORS_TEST_KEY}


def test_forward_swaps_ors_lng_lat_order(fake_ors, pelias_search_denver):
    fake_ors.payloads = [pelias_search_denver]

    lat, lng, _ = geocode.forward("Denver, CO")

    assert -90 <= lat <= 90  # an unswapped -104.99 could never pass
    assert (lat, lng) == (39.7392, -104.9903)


@pytest.mark.parametrize(
    ("properties", "label"),
    [
        ({"locality": "Cheyenne", "county": "Laramie County", "region": "Wyoming", "region_a": "WY"}, "Cheyenne, WY"),
        ({"locality": "", "county": "Laramie County", "region": "Wyoming", "region_a": "WY"}, "Laramie County, WY"),
        ({"region": "Wyoming", "region_a": "WY"}, "Wyoming, WY"),
    ],
    ids=["locality", "county", "region"],
)
def test_label_falls_back_through_locality_county_region(fake_ors, properties, label):
    fake_ors.payloads = [{"features": [pelias_feature(-104.8202, 41.14, **properties)]}]

    assert geocode.reverse(41.14, -104.8202) == label


@pytest.mark.parametrize(
    "properties",
    [{"region_a": "WY"}, {"locality": "Cheyenne", "region": "Wyoming"}, {}],
    ids=["no-place", "no-state-abbreviation", "nothing"],
)
def test_no_usable_label_raises_not_found(fake_ors, properties):
    fake_ors.payloads = [{"features": [pelias_feature(-104.8202, 41.14, **properties)]}]

    with pytest.raises(http.NotFoundError):
        geocode.reverse(41.14, -104.8202)


def test_empty_results_raise_not_found(fake_ors, pelias_empty):
    fake_ors.payloads = [pelias_empty]

    with pytest.raises(http.NotFoundError):
        geocode.forward("Nowhere, ZZ")
    with pytest.raises(http.NotFoundError):
        geocode.reverse(0.0, -150.0)


def test_malformed_payload_raises_upstream_error(fake_ors):
    fake_ors.payloads = [{"features": [{"type": "Feature", "properties": {}}]}]

    with pytest.raises(http.UpstreamError):
        geocode.forward("Denver, CO")


@pytest.mark.parametrize("address", ["", "   ", "\t\n"])
def test_blank_address_raises_before_any_call(fake_ors, address):
    with pytest.raises(ValueError):
        geocode.forward(address)

    assert fake_ors.calls == []


def test_repeated_forward_calls_hit_the_network_once(fake_ors, pelias_search_denver):
    fake_ors.payloads = [pelias_search_denver]

    results = {geocode.forward(text) for text in ("Denver, CO", "denver, co", "  Denver,   CO ", "DENVER, CO")}

    assert results == {(39.7392, -104.9903, "Denver, CO")}
    assert len(fake_ors.calls) == 1


def test_reverse_cache_keys_on_three_decimals(fake_ors, pelias_reverse_cheyenne):
    fake_ors.payloads = [pelias_reverse_cheyenne]

    geocode.reverse(41.14012, -104.82021)
    geocode.reverse(41.14038, -104.81979)  # differs only below the third decimal
    assert len(fake_ors.calls) == 1
    assert fake_ors.calls[0][2]["params"] == {"point.lat": 41.14, "point.lon": -104.82, "size": 1}

    geocode.reverse(41.141, -104.82)  # differs at the third decimal
    assert len(fake_ors.calls) == 2
