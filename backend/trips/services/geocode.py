"""Address geocoding via OpenRouteService Pelias, cached by normalized address. Touches the network."""
import re
from functools import lru_cache

from . import geocode_cache, http
from .errors import NotFoundError, UpstreamError

SEARCH_URL = f"{http.ORS_BASE_URL}/geocode/search"
REVERSE_URL = f"{http.ORS_BASE_URL}/geocode/reverse"
REVERSE_CACHE_DECIMALS = 3  # about 110 metres of latitude
REVERSE_RADIUS_KM = 15
REVERSE_FALLBACK_RADIUS_KM = 150  # rural interstates often have no locality within the first radius
# Addresses, not admin layers: Pelias answers an all-admin layer list with a point-in-polygon lookup that ignores the
# radius ("not applicable for coarse reverse") and returns the county whenever the point is outside town limits.
# Nearby addresses carry the town they belong to, and the radius is honoured.
REVERSE_LAYERS = "address"
REVERSE_SIZE = 10  # rural addresses often carry only a county, so look past the nearest few for a town
CACHE_SIZE = 1024
TRAILING_STATE_CODE = re.compile(r"[\s,]([a-z]{2})$")  # "denver, co" -> "co"


def forward(address):
    """(lat, lng, "City, ST") for a US address. Raises ValueError for a blank address, NotFoundError for no match.

    Pelias almost never answers "no match": live, "Atlantis, ZZ" returns Atlantis, FL and "123 Main St, Nowhere, TX"
    returns Nowhere, OK. So when the address ends in a two-letter state code, a match in another state is no match.
    """
    normalized = " ".join(address.lower().split())
    if not normalized:
        raise ValueError("address must not be blank")
    lat, lng, label = _forward(normalized)
    state = TRAILING_STATE_CODE.search(normalized)
    if state and not label.lower().endswith(f", {state.group(1)}"):
        raise NotFoundError(f"no match for {address!r} in {state.group(1).upper()}; the closest was {label}")
    return lat, lng, label


def reverse(lat, lng):
    """"City, ST" for a coordinate, widening the search radius once. NotFoundError when neither radius finds a place."""
    key = (round(lat, REVERSE_CACHE_DECIMALS), round(lng, REVERSE_CACHE_DECIMALS))
    label = _reverse(*key, REVERSE_RADIUS_KM) or _reverse(*key, REVERSE_FALLBACK_RADIUS_KM)
    if label is None:
        raise NotFoundError(f"no place within {REVERSE_FALLBACK_RADIUS_KM} km of {key}")
    return label


def clear_caches():
    _forward.cache_clear()
    _reverse.cache_clear()


@lru_cache(maxsize=CACHE_SIZE)
def _forward(normalized_address):
    """Per process first, then the database, then ORS. Hits and misses are stored; upstream failures are not."""
    cached = geocode_cache.lookup(geocode_cache.FORWARD, normalized_address)
    if cached is not None:
        if cached.label is None:
            raise NotFoundError(f"no geocoding match for {normalized_address!r}")
        return cached.lat, cached.lng, cached.label

    payload = http.request_json(
        "GET",
        SEARCH_URL,
        params={"text": normalized_address, "size": 1, "boundary.country": "US"},
        headers=http.ors_headers(),
    )
    try:
        lat, lng, label = _first_place(payload, normalized_address)
    except NotFoundError:
        geocode_cache.store(geocode_cache.FORWARD, normalized_address, None)
        raise
    geocode_cache.store(geocode_cache.FORWARD, normalized_address, label, lat, lng)
    return lat, lng, label


@lru_cache(maxsize=CACHE_SIZE)
def _reverse(lat, lng, radius_km):
    """Label, or None on a miss so the miss is cached too. Upstream failures raise and are not cached."""
    key = geocode_cache.reverse_key(lat, lng, radius_km)
    cached = geocode_cache.lookup(geocode_cache.REVERSE, key)
    if cached is not None:
        return cached.label

    payload = http.request_json(
        "GET",
        REVERSE_URL,
        params={
            "point.lat": lat,
            "point.lon": lng,
            "size": REVERSE_SIZE,
            "boundary.circle.radius": radius_km,
            "layers": REVERSE_LAYERS,
        },
        headers=http.ors_headers(),
    )
    label = _nearest_place_label(payload, f"{lat},{lng}")
    geocode_cache.store(geocode_cache.REVERSE, key, label)
    return label


def _nearest_place_label(payload, query):
    """"Town, ST" from the nearest feature naming a locality, then a localadmin, then a county; None when none does.

    Pelias sorts features by distance, so within each field the first match is the nearest.
    """
    try:
        places = [feature["properties"] for feature in payload["features"]]
        for field in ("locality", "localadmin", "county"):
            for place in places:
                if place.get(field) and place.get("region_a"):
                    return f"{place[field]}, {place['region_a']}"
    except (KeyError, TypeError, AttributeError) as error:
        raise UpstreamError(f"malformed geocoding response for {query!r}") from error
    return None


def _first_place(payload, query):
    """(lat, lng, label) from the first Pelias feature, swapping ORS's [lng, lat] at this boundary."""
    try:
        features = payload["features"]
        if not features:
            raise NotFoundError(f"no geocoding match for {query!r}")
        feature = features[0]
        lng, lat = (float(value) for value in feature["geometry"]["coordinates"][:2])
        properties = feature["properties"]
        place = properties.get("locality") or properties.get("localadmin") or properties.get("county")
        state = properties.get("region_a")
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise UpstreamError(f"malformed geocoding response for {query!r}") from error
    if not place or not state:
        raise NotFoundError(f"no usable place name for {query!r}")
    return lat, lng, f"{place}, {state}"
