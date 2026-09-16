"""Trip orchestration, the only module aware of both geo and HOS.

Geocode the inputs, route them, drive the pure HOS engine along the route, name every stop, and turn
minutes since trip start into wall-clock times in the home terminal zone. The HOS package never sees
a datetime; this module is where they come back in.
"""
import math
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import geocode, routing
from .errors import InputError, NotFoundError, UpstreamError
from .hos import constants
from .hos.constants import (
    DROPOFF_DURATION_MIN,
    GRID_RESOLUTION_MIN,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    PICKUP_DURATION_MIN,
)
from .hos.engine import plan_duty
from .hos.enums import DutyStatus, StopKind
from .hos.events import Waypoint
from .hos.segments import split_at_midnight
from .hos.sheets import DaySheet, build_sheets
from .hos.state import DriverState, replay
from .route_index import RouteIndex, road_at

SAME_PLACE_EPSILON_DEG = 0.001  # about 110 m: two geocoded inputs closer than this are one place
ORS_COORDINATE_INDEX = re.compile(r"coordinate (\d+)")  # ORS error 2010 names the 0-based index of the bad point


@dataclass(frozen=True)
class Stop:
    kind: StopKind
    at_mile: float
    lat: float
    lng: float
    label: str
    arrive: datetime
    depart: datetime
    duration_hours: float


@dataclass(frozen=True)
class DatedSheet:
    """A DaySheet with its calendar date in the home terminal zone. DaySheet itself stays datetime-free."""

    date: date
    sheet: DaySheet


@dataclass(frozen=True)
class TripSummary:
    total_miles: float
    driving_hours: float
    elapsed_hours: float
    days: int
    cycle_used_at_end: float  # hours, the live 8-day cycle when the trip ends
    restart_required: bool


@dataclass(frozen=True)
class TripPlan:
    route: routing.Route
    events: list  # located DutyEvents, the engine's full timeline
    stops: list[Stop]
    sheets: list[DatedSheet]
    summary: TripSummary
    limits: dict[str, int]


def plan_trip(current, pickup, dropoff, cycle_used_min, start_time, tz_name):
    """Plan a property-carrying trip from the current location via pickup to dropoff.

    Raises NotFoundError naming the input that could not be geocoded, or when no truck route exists;
    UpstreamError when ORS fails; InputError when start_time is not on the 15-minute grid.
    """
    zone = ZoneInfo(tz_name)
    local_start = _localize(start_time, zone)
    midnight = minutes_to_first_midnight(local_start, tz_name)

    roles = ("current location", "pickup location", "dropoff location")
    places = [_geocode_input(role, address) for role, address in zip(roles, (current, pickup, dropoff))]
    if _same_place(places[1], places[2]):
        raise NotFoundError(
            f"The pickup location ({places[1][2]}) and dropoff location ({places[2][2]}) are the same place."
        )
    # Starting at the pickup: route two points rather than rely on ORS accepting a zero-length leg.
    starts_at_pickup = _same_place(places[0], places[1])
    routed = [(roles[0], places[0]), (roles[2], places[2])] if starts_at_pickup else list(zip(roles, places))
    route = _route(routed)
    index = RouteIndex(route.geometry, route.total_miles)

    pickup_mile = 0.0 if starts_at_pickup else min(route.leg_miles[0], route.total_miles)
    waypoints = (
        Waypoint(0.0, StopKind.START, places[0][2], 0),
        Waypoint(pickup_mile, StopKind.PICKUP, places[1][2], PICKUP_DURATION_MIN),
        Waypoint(route.total_miles, StopKind.DROPOFF, places[2][2], DROPOFF_DURATION_MIN),
    )

    prior_cycle_min = math.ceil(cycle_used_min)  # round up so a fractional minute is never under-counted
    initial_state = DriverState.initial(prior_cycle_min)
    raw_events = plan_duty(waypoints, initial_state, midnight)

    labels = _name_miles(raw_events, index, route.named_points, waypoints)
    events = [replace(event, location=labels[event.at_mile]) for event in raw_events]

    sheets = build_sheets(
        split_at_midnight(events, midnight), midnight, prior_cycle_min, restart_day_indices(events, midnight)
    )

    return TripPlan(
        route=route,
        events=events,
        stops=_stops(events, waypoints[0], index, local_start),
        sheets=[DatedSheet(local_start.date() + timedelta(days=sheet.date_index), sheet) for sheet in sheets],
        summary=_summary(events, route, len(sheets), replay(events, initial_state, midnight)),
        limits=limits(),
    )


def minutes_to_first_midnight(start_time, tz_name):
    """Wall-clock minutes from start_time to the next home-terminal midnight, 1 to 1440; exactly midnight gives 1440.

    Wall-clock, not elapsed: the HOS layer treats every day as 1440 minutes, so the sheets' day boundaries stay
    on local midnight. On a daylight-saving changeover the timeline drifts by that hour; see the step report.
    """
    local = _localize(start_time, ZoneInfo(tz_name))
    return MINUTES_PER_DAY - (local.hour * MINUTES_PER_HOUR + local.minute)


def restart_day_indices(events, minutes_to_first_midnight):
    """Day indices on which a 34-hour restart completes. Day 0 is the minutes before the first midnight."""
    return frozenset(
        (event.end_min - minutes_to_first_midnight) // MINUTES_PER_DAY + 1
        for event in events
        if event.kind is StopKind.RESTART
    )


def limits():
    """Every public integer constant, keyed in lower case, so a new limit reaches the API without another edit."""
    return {
        name.lower(): value
        for name, value in vars(constants).items()
        if name.isupper() and not name.startswith("_") and type(value) is int
    }


def _localize(start_time, zone):
    local = start_time.astimezone(zone) if start_time.tzinfo else start_time.replace(tzinfo=zone)
    if local.minute % GRID_RESOLUTION_MIN or local.second or local.microsecond:
        raise InputError(f"start_time must fall on a {GRID_RESOLUTION_MIN}-minute boundary, got {local.isoformat()}")
    return local


def _same_place(first, second):
    return abs(first[0] - second[0]) <= SAME_PLACE_EPSILON_DEG and abs(first[1] - second[1]) <= SAME_PLACE_EPSILON_DEG


def _geocode_input(role, address):
    try:
        return geocode.forward(address)
    except NotFoundError as error:
        raise NotFoundError(f"Could not find the {role}: {address!r}") from error


def _route(routed):
    """Route (role, place) pairs, rewriting "no route" errors to name the input a driver would recognise."""
    try:
        return routing.route([(lat, lng) for _, (lat, lng, _) in routed])
    except NotFoundError as error:
        raise NotFoundError(_unroutable_message(str(error), routed)) from error


def _unroutable_message(upstream_message, routed):
    """Best effort: ORS names the failing point by its index in the routed list, which may be two points or three."""
    match = ORS_COORDINATE_INDEX.search(upstream_message)
    if match and int(match.group(1)) < len(routed):
        role, (_, _, label) = routed[int(match.group(1))]
        return f"No truck-accessible road was found near the {role} ({label})."
    return "No drivable truck route connects these locations."


def _name_miles(events, index, named_points, waypoints):
    """One label per distinct mile. Waypoint miles use the geocoded input names; every other mile goes
    through the stop-naming chain once, however many events share it."""
    labels = {waypoint.at_mile: waypoint.label for waypoint in waypoints}
    anchors = [(waypoint.at_mile, waypoint.label) for waypoint in waypoints]
    for event in events:
        if event.at_mile not in labels:
            labels[event.at_mile] = _name_mile(event.at_mile, index, named_points, anchors)
    return labels


def _name_mile(mile, index, named_points, anchors):
    """§15 chain: reverse geocode (the geocode module widens the radius once), then "<road> near <city>"."""
    lat, lng = index.coordinate_at(mile)
    try:
        return geocode.reverse(lat, lng)
    except (NotFoundError, UpstreamError):
        pass  # naming is best effort; a flaky reverse lookup must not fail a plan that already has its route
    _, city = min(anchors, key=lambda anchor: abs(anchor[0] - mile))
    road = road_at(mile, named_points)
    return f"{road} near {city}" if road else f"Near {city}"


def _stops(events, start, index, local_start):
    """START, then one stop per run of adjacent events sharing both kind and mile."""
    runs = [[start.kind, start.at_mile, start.label, 0, 0]]
    for event in events:
        if event.kind is None:
            continue
        last = runs[-1]
        if last[0] is event.kind and last[1] == event.at_mile and last[4] == event.start_min:
            last[4] = event.end_min
        else:
            runs.append([event.kind, event.at_mile, event.location, event.start_min, event.end_min])

    stops = []
    for kind, mile, label, start_min, end_min in runs:
        lat, lng = index.coordinate_at(mile)
        stops.append(Stop(
            kind=kind,
            at_mile=mile,
            lat=lat,
            lng=lng,
            label=label,
            arrive=local_start + timedelta(minutes=start_min),
            depart=local_start + timedelta(minutes=end_min),
            duration_hours=(end_min - start_min) / MINUTES_PER_HOUR,
        ))
    return stops


def _summary(events, route, day_count, final_state):
    driving_min = sum(event.duration_min for event in events if event.status is DutyStatus.DRIVING)
    return TripSummary(
        total_miles=route.total_miles,
        driving_hours=driving_min / MINUTES_PER_HOUR,
        elapsed_hours=(events[-1].end_min if events else 0) / MINUTES_PER_HOUR,
        days=day_count,
        cycle_used_at_end=final_state.cycle_min / MINUTES_PER_HOUR,
        restart_required=any(event.kind is StopKind.RESTART for event in events),
    )
