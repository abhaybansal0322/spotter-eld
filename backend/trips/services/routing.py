"""Truck routing via OpenRouteService driving-hgv. Touches the network."""
from dataclasses import dataclass

from . import http

DIRECTIONS_URL = f"{http.ORS_BASE_URL}/v2/directions/driving-hgv/geojson"
PLACEHOLDER_STEP_NAMES = frozenset({"", "-"})
ORS_NOT_FOUND_STATUS = 404  # ORS answers 404 when a point is unroutable or no route exists


@dataclass(frozen=True)
class Route:
    geometry: list[tuple[float, float]]  # (lat, lng)
    total_miles: float  # road distance, as ORS reports it
    named_points: list[tuple[float, str]]  # (mile at step start, road name), sorted by mile
    bbox: tuple[tuple[float, float], tuple[float, float]]  # ((south, west), (north, east)), Leaflet's bounds order


def route(coordinates):
    """Driving-hgv route through (lat, lng) coordinates in order. NotFoundError when no route exists."""
    if len(coordinates) < 2:
        raise ValueError("a route needs at least two coordinates")
    body = {"coordinates": [[lng, lat] for lat, lng in coordinates], "units": "mi"}
    try:
        payload = http.request_json("POST", DIRECTIONS_URL, json=body, headers=http.ors_headers())
    except http.UpstreamError as error:
        if error.status == ORS_NOT_FOUND_STATUS:
            raise http.NotFoundError("no drivable truck route between these locations") from error
        raise

    try:
        features = payload["features"]
        if not features:
            raise http.NotFoundError("no drivable truck route between these locations")
        return _parse(features[0])
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise http.UpstreamError("malformed routing response") from error


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
        named_points=named_points,
        bbox=((float(south), float(west)), (float(north), float(east))),
    )
