"""Geocode tests with the network mocked at the http.request_json seam."""
import pytest
from django.db import DatabaseError

from tests.conftest import ORS_TEST_KEY, pelias_feature
from trips.models import GeocodeCache
from trips.services import geocode, geocode_cache, http

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
        ({"locality": "", "localadmin": "Cheyenne Township", "county": "Laramie County", "region_a": "WY"}, "Cheyenne Township, WY"),
        ({"county": "Laramie County", "region": "Wyoming", "region_a": "WY"}, "Laramie County, WY"),
    ],
    ids=["locality", "localadmin", "county"],
)
def test_label_falls_back_through_locality_localadmin_county(fake_ors, properties, label):
    fake_ors.payloads = [{"features": [pelias_feature(-104.8202, 41.14, **properties)]}]

    assert geocode.reverse(41.14, -104.8202) == label


@pytest.mark.parametrize(
    "properties",
    [{"region_a": "WY"}, {"region": "Wyoming", "region_a": "WY"}, {"locality": "Cheyenne", "region": "Wyoming"}, {}],
    ids=["no-place", "region-is-not-a-place", "no-state-abbreviation", "nothing"],
)
def test_no_usable_label_raises_not_found(fake_ors, properties):
    fake_ors.payloads = [{"features": [pelias_feature(-104.8202, 41.14, **properties)]}]

    with pytest.raises(http.NotFoundError):
        geocode.reverse(41.14, -104.8202)


@pytest.mark.parametrize(
    ("address", "locality", "state"),
    [("Atlantis, ZZ", "Atlantis", "FL"), ("123 Main St, Nowhere, TX", "Nowhere", "OK")],
    ids=["unknown-state-code", "wrong-state"],
)
def test_forward_match_in_another_state_than_the_address_names_is_not_found(fake_ors, address, locality, state):
    # Both are what live Pelias returns for these inputs instead of an empty result.
    fake_ors.payloads = [{"features": [pelias_feature(-80.0, 26.6, locality=locality, region_a=state)]}]

    with pytest.raises(http.NotFoundError):
        geocode.forward(address)


@pytest.mark.parametrize("address", ["Denver, CO", "denver co", "Denver", "Denver, Colorado"])
def test_forward_accepts_a_match_in_the_named_state_or_when_no_code_is_given(fake_ors, pelias_search_denver, address):
    fake_ors.payloads = [pelias_search_denver]

    assert geocode.forward(address)[2] == "Denver, CO"


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
    assert fake_ors.calls[0][2]["params"] == {
        "point.lat": 41.14, "point.lon": -104.82, "size": 10,
        "boundary.circle.radius": 15, "layers": "address",
    }

    geocode.reverse(41.141, -104.82)  # differs at the third decimal
    assert len(fake_ors.calls) == 2


def test_reverse_prefers_the_nearest_town_over_nearer_county_only_addresses(fake_ors):
    # Live shape: rural addresses near I-80 carry only a county; the first one naming a town is a few features further.
    fake_ors.payloads = [{"features": [
        pelias_feature(-111.71, 38.91, name="11001 County Road 28", county="Sevier County", region_a="UT", distance=2.1),
        pelias_feature(-111.80, 38.95, name="Gooseberry Road", localadmin="Gooseberry Township", county="Sevier County", region_a="UT", distance=6.0),
        pelias_feature(-111.86, 38.96, name="581 South State Street", locality="Salina", county="Sevier County", region_a="UT", distance=12.4),
    ]}]

    assert geocode.reverse(38.912, -111.713) == "Salina, UT"


def test_reverse_falls_back_to_the_county_when_no_address_names_a_town(fake_ors):
    fake_ors.payloads = [{"features": [
        pelias_feature(-102.44, 40.92, name="11001 County Road 28", county="Sedgwick County", region_a="CO"),
        pelias_feature(-102.45, 40.93, name="723 Saunders Avenue", county="Sedgwick County", region_a="CO"),
    ]}]

    assert geocode.reverse(40.924, -102.448) == "Sedgwick County, CO"


def test_reverse_widens_radius_once_on_a_miss(fake_ors, pelias_empty, pelias_reverse_cheyenne):
    fake_ors.payloads = [pelias_empty, pelias_reverse_cheyenne]

    assert geocode.reverse(41.14, -104.8202) == "Cheyenne, WY"
    assert [call[2]["params"]["boundary.circle.radius"] for call in fake_ors.calls] == [
        geocode.REVERSE_RADIUS_KM, geocode.REVERSE_FALLBACK_RADIUS_KM,
    ]


def test_repeated_reverse_miss_is_cached(fake_ors, pelias_empty):
    fake_ors.payloads = [pelias_empty]

    for _ in range(3):
        with pytest.raises(http.NotFoundError):
            geocode.reverse(44.5, -107.5)

    # The first lookup tries both radii; the misses are cached, so repeats make no further calls.
    assert len(fake_ors.calls) == 2


def test_reverse_upstream_failure_is_not_cached(monkeypatch, pelias_reverse_cheyenne):
    outcomes = [http.UpstreamError("ORS down", status=503), pelias_reverse_cheyenne]
    calls = []

    def flaky(method, url, **kwargs):
        calls.append(kwargs["params"]["boundary.circle.radius"])
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(http, "request_json", flaky)

    with pytest.raises(http.UpstreamError):
        geocode.reverse(41.14, -104.8202)
    assert geocode.reverse(41.14, -104.8202) == "Cheyenne, WY"
    assert calls == [15, 15]


# Persistent cache (spec §28). lru_cache is cleared between steps to stand in for a fresh process.


def test_cached_answers_are_served_without_the_network(fake_ors):
    GeocodeCache.objects.create(kind="forward", key="denver, co", label="Denver, CO", lat=39.7392, lng=-104.9903)
    GeocodeCache.objects.create(kind="reverse", key=geocode_cache.reverse_key(41.14, -104.82, geocode.REVERSE_RADIUS_KM), label="Cheyenne, WY")

    assert geocode.forward("  Denver,  CO ") == (39.7392, -104.9903, "Denver, CO")
    assert geocode.reverse(41.14012, -104.82021) == "Cheyenne, WY"
    assert fake_ors.calls == []


def test_misses_are_stored_and_never_queried_again(fake_ors, pelias_empty):
    fake_ors.payloads = [pelias_empty]

    for _ in range(2):
        with pytest.raises(http.NotFoundError):
            geocode.forward("Nowhere, ZZ")
        with pytest.raises(http.NotFoundError):
            geocode.reverse(44.5, -107.5)
        geocode.clear_caches()

    assert len(fake_ors.calls) == 3  # one search and two reverse radii, all on the first pass
    assert set(GeocodeCache.objects.values_list("kind", "key", "label")) == {
        ("forward", "nowhere, zz", None),
        ("reverse", "44.500,-107.500,15", None),
        ("reverse", "44.500,-107.500,150", None),
    }


def test_the_table_returns_what_the_network_and_lru_cache_returned(fake_ors, pelias_search_denver, pelias_reverse_cheyenne):
    fake_ors.payloads = [pelias_search_denver]
    live_forward = geocode.forward("Denver, CO")
    fake_ors.payloads = [pelias_search_denver, pelias_reverse_cheyenne]
    live_reverse = geocode.reverse(41.14, -104.8202)

    assert geocode.forward("Denver, CO") == live_forward  # lru layer
    geocode.clear_caches()
    assert geocode.forward("Denver, CO") == live_forward  # table layer
    assert geocode.reverse(41.14, -104.8202) == live_reverse
    assert len(fake_ors.calls) == 2


def test_forward_and_reverse_entries_never_collide(fake_ors, pelias_reverse_cheyenne):
    key = geocode_cache.reverse_key(41.14, -104.82, geocode.REVERSE_RADIUS_KM)
    GeocodeCache.objects.create(kind="forward", key=key, label="Wrong Kind, XX", lat=0.0, lng=0.0)
    fake_ors.payloads = [pelias_reverse_cheyenne]

    assert geocode.reverse(41.14, -104.82) == "Cheyenne, WY"
    assert len(fake_ors.calls) == 1
    assert GeocodeCache.objects.filter(key=key).count() == 2


def test_a_broken_cache_table_degrades_to_the_network(fake_ors, pelias_search_denver, monkeypatch):
    def fail(*args, **kwargs):
        raise DatabaseError("disk full")

    monkeypatch.setattr(GeocodeCache.objects, "update_or_create", fail)
    fake_ors.payloads = [pelias_search_denver]
    assert geocode.forward("Denver, CO") == (39.7392, -104.9903, "Denver, CO")

    monkeypatch.setattr(GeocodeCache.objects, "filter", fail)
    geocode.clear_caches()
    assert geocode.forward("Denver, CO") == (39.7392, -104.9903, "Denver, CO")
    assert len(fake_ors.calls) == 2


@pytest.mark.parametrize("status", [403, 500], ids=["quota-403", "server-500"])
def test_quota_and_server_failures_are_never_cached_for_either_kind(monkeypatch, pelias_search_denver, pelias_reverse_cheyenne, status):
    outcomes = [http.UpstreamError("ORS failed", status=status), http.UpstreamError("ORS failed", status=status),
                pelias_search_denver, pelias_reverse_cheyenne]
    calls = []

    def flaky(method, url, **kwargs):
        calls.append(url)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(http, "request_json", flaky)

    with pytest.raises(http.UpstreamError):
        geocode.forward("Denver, CO")
    with pytest.raises(http.UpstreamError):
        geocode.reverse(41.14, -104.8202)
    assert not GeocodeCache.objects.exists()

    assert geocode.forward("Denver, CO")[2] == "Denver, CO"  # retried, not served a frozen failure
    assert geocode.reverse(41.14, -104.8202) == "Cheyenne, WY"
    assert len(calls) == 4
