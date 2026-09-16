"""Truck routing via OpenRouteService driving-hgv. Touches the network."""
from dataclasses import dataclass

from . import http
from .errors import NotFoundError, UpstreamError

DIRECTIONS_URL = f"{http.ORS_BASE_URL}/v2/directions/driving-hgv/geojson"
PLACEHOLDER_STEP_NAMES = frozenset({"", "-"})
ORS_NOT_FOUND_STATUS = 404
ORS_BAD_REQUEST_STATUS = 400
# 2004 route longer than the ORS limit, 2009 no route found, 2010 point not routable: bad input, not a server fault
ORS_NOT_FOUND_CODES = frozenset({2004, 2009, 2010})
NO_ROUTE_MESSAGE = "no drivable truck route between these locations"


@dataclass(frozen=True)
class Route:
    geometry: list[tuple[float, float]]  # (lat, lng)
    total_miles: float  # road distance, as ORS reports it
    leg_miles: list[float]  # road distance of each leg between consecutive input coordinates
    named_points: list[tuple[float, str]]  # (mile at step start, road name), sorted by mile
    bbox: tuple[tuple[float, float], tuple[float, float]]  # ((south, west), (north, east)), Leaflet's bounds order


def route(coordinates):
    """Driving-hgv route through (lat, lng) coordinates in order. NotFoundError when no route exists."""
    if len(coordinates) < 2:
        raise ValueError("a route needs at least two coordinates")
    body = {"coordinates": [[lng, lat] for lat, lng in coordinates], "units": "mi"}
    try:
        payload = http.request_json("POST", DIRECTIONS_URL, json=body, headers=http.ors_headers())
    except UpstreamError as error:
        not_found = _as_not_found(error)
        if not_found:
            raise not_found from error
        raise

    try:
        features = payload["features"]
        if not features:
            raise NotFoundError(NO_ROUTE_MESSAGE)
        return _parse(features[0])
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise UpstreamError("malformed routing response") from error


def _as_not_found(error):
    """NotFoundError carrying ORS's own message when the failure means "no such route", else None."""
    details = error.body.get("error") if isinstance(error.body, dict) else None
    code = details.get("code") if isinstance(details, dict) else None
    message = details.get("message") if isinstance(details, dict) else None
    if error.status == ORS_NOT_FOUND_STATUS or (error.status == ORS_BAD_REQUEST_STATUS and code in ORS_NOT_FOUND_CODES):
        return NotFoundError(message or NO_ROUTE_MESSAGE)
    return None


def _parse(feature):
    """Swap ORS's [lng, lat] at this boundary and pair each named step with its starting road mile."""
    geometry = [(float(lat), float(lng)) for lng, lat, *_ in feature["geometry"]["coordinates"]]
    properties = feature["properties"]

    named_points = []
    mile = 0.0
    for segment in properties["segments"]:
        for step in segment["steps"]:
            name = step.get("name", "").strip()
            if name not in PLACEHOLDER_STEP_NAMES:
                named_points.append((mile, name))
            mile += float(step["distance"])

    west, south, east, north = feature["bbox"]
    return Route(
        geometry=geometry,
        total_miles=float(properties["summary"]["distance"]),
        leg_miles=[float(segment.get("distance", 0.0)) for segment in properties["segments"]],
        named_points=named_points,
        bbox=((float(south), float(west)), (float(north), float(east))),
    )
