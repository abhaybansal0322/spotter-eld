"""Address geocoding via OpenRouteService Pelias, cached by normalized address. Touches the network."""
from functools import lru_cache

from . import http

SEARCH_URL = f"{http.ORS_BASE_URL}/geocode/search"
REVERSE_URL = f"{http.ORS_BASE_URL}/geocode/reverse"
REVERSE_CACHE_DECIMALS = 3  # about 110 metres of latitude
REVERSE_RADIUS_KM = 25
REVERSE_FALLBACK_RADIUS_KM = 150  # rural interstates often have no locality within the first radius
REVERSE_LAYERS = "locality,localadmin,county"
CACHE_SIZE = 1024


def forward(address):
    """(lat, lng, "City, ST") for a US address. Raises ValueError for a blank address, NotFoundError for no match."""
    normalized = " ".join(address.lower().split())
    if not normalized:
        raise ValueError("address must not be blank")
    return _forward(normalized)


def reverse(lat, lng):
    """"City, ST" for a coordinate, widening the search radius once. NotFoundError when neither radius finds a place."""
    key = (round(lat, REVERSE_CACHE_DECIMALS), round(lng, REVERSE_CACHE_DECIMALS))
    label = _reverse(*key, REVERSE_RADIUS_KM) or _reverse(*key, REVERSE_FALLBACK_RADIUS_KM)
    if label is None:
        raise http.NotFoundError(f"no place within {REVERSE_FALLBACK_RADIUS_KM} km of {key}")
    return label


def clear_caches():
    _forward.cache_clear()
    _reverse.cache_clear()


@lru_cache(maxsize=CACHE_SIZE)
def _forward(normalized_address):
    payload = http.request_json(
        "GET",
        SEARCH_URL,
        params={"text": normalized_address, "size": 1, "boundary.country": "US"},
        headers=http.ors_headers(),
    )
    lat, lng, label = _first_place(payload, normalized_address)
    return lat, lng, label


@lru_cache(maxsize=CACHE_SIZE)
def _reverse(lat, lng, radius_km):
    """Label, or None on a miss so the miss is cached too. Upstream failures raise and are not cached."""
    payload = http.request_json(
        "GET",
        REVERSE_URL,
        params={
            "point.lat": lat,
            "point.lon": lng,
            "size": 1,
            "boundary.circle.radius": radius_km,
            "layers": REVERSE_LAYERS,
        },
        headers=http.ors_headers(),
    )
    try:
        return _first_place(payload, f"{lat},{lng}")[2]
    except http.NotFoundError:
        return None


def _first_place(payload, query):
    """(lat, lng, label) from the first Pelias feature, swapping ORS's [lng, lat] at this boundary."""
    try:
        features = payload["features"]
        if not features:
            raise http.NotFoundError(f"no geocoding match for {query!r}")
        feature = features[0]
        lng, lat = (float(value) for value in feature["geometry"]["coordinates"][:2])
        properties = feature["properties"]
        place = properties.get("locality") or properties.get("localadmin") or properties.get("county")
        state = properties.get("region_a")
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise http.UpstreamError(f"malformed geocoding response for {query!r}") from error
    if not place or not state:
        raise http.NotFoundError(f"no usable place name for {query!r}")
    return lat, lng, f"{place}, {state}"
