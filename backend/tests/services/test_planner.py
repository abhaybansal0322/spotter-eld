"""Planner orchestration tests. ORS is faked at http.request_json; no live calls."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import BASE_LNG, directions_payload, north_of_base, straight_trip
from trips.services import geocode, http, planner, routing
from trips.services.hos import constants
from trips.services.hos.constants import MINUTES_PER_DAY
from trips.services.hos.enums import DutyStatus, StopKind

pytestmark = pytest.mark.usefixtures("ors")

NEW_YORK = "America/New_York"


def _plan(start="2026-09-16T06:00", tz=NEW_YORK, cycle_used_min=0):
    return planner.plan_trip(
        "Origin, AA", "Pickup, BB", "Dropoff, CC", cycle_used_min, datetime.fromisoformat(start).replace(tzinfo=ZoneInfo(tz)), tz
    )


def _kinds(plan):
    return [stop.kind for stop in plan.stops]


def test_short_single_day_trip(fake_ors):
    fake = fake_ors(straight_trip(55, 110))

    plan = _plan()

    assert len(fake.urls(geocode.SEARCH_URL)) == 3
    assert len(fake.urls(routing.DIRECTIONS_URL)) == 1
    assert fake.urls(geocode.REVERSE_URL) == []  # every event sits at a waypoint, already named
    assert len(plan.sheets) == 1
    assert _kinds(plan) == [StopKind.START, StopKind.PICKUP, StopKind.DROPOFF]
    assert [stop.label for stop in plan.stops] == ["Origin, AA", "Pickup, BB", "Dropoff, CC"]


def test_multi_day_trip_sheets_are_full_days(fake_ors):
    fake_ors(straight_trip(100, 2000))

    plan = _plan(cycle_used_min=600)

    assert len(plan.sheets) == 4
    for dated in plan.sheets:
        assert sum(dated.sheet.totals.values()) == MINUTES_PER_DAY
    assert [dated.date.isoformat() for dated in plan.sheets] == ["2026-09-16", "2026-09-17", "2026-09-18", "2026-09-19"]
    assert _kinds(plan).count(StopKind.FUEL) == 2
    assert all(event.location for event in plan.events)


def test_pickup_waypoint_lands_on_first_leg_distance(fake_ors):
    fake_ors(straight_trip(100, 2000))

    plan = _plan(cycle_used_min=600)

    (pickup,) = [stop for stop in plan.stops if stop.kind is StopKind.PICKUP]
    assert pickup.at_mile == 100.0  # leg_miles[0], not half of 2000
    assert pickup.lat == pytest.approx(north_of_base(100)[0])


def test_stop_split_at_midnight_is_one_stop_and_two_events(fake_ors):
    fake_ors(straight_trip(55, 110))

    plan = _plan(start="2026-09-16T22:30")  # drive 60 min, pickup 23:30 to 00:30

    assert len([event for event in plan.events if event.kind is StopKind.PICKUP]) == 2
    (pickup,) = [stop for stop in plan.stops if stop.kind is StopKind.PICKUP]
    assert pickup.duration_hours == 1.0
    assert (pickup.arrive.isoformat(), pickup.depart.isoformat()) == (
        "2026-09-16T23:30:00-04:00", "2026-09-17T00:30:00-04:00",
    )


def _midnight_drive_trip():
    """Starts 23:30: the first leg is cut at midnight, so exactly one event sits at a mile with no waypoint."""
    return straight_trip(110, 220)


def test_naming_tier_1_reverse_label_used_verbatim(fake_ors):
    fake = fake_ors(_midnight_drive_trip(), reverse=lambda lat, lng, radius: "Amarillo")

    plan = _plan(start="2026-09-16T23:30")

    (unnamed_mile,) = {event.at_mile for event in plan.events} - {0.0, 110.0, 220.0}
    assert [event.location for event in plan.events if event.at_mile == unnamed_mile] == ["Amarillo, XX"]
    assert [params["boundary.circle.radius"] for params in fake.urls(geocode.REVERSE_URL)] == [25]
    assert plan.sheets[1].sheet.remarks[0] == (0, "Amarillo, XX")


def test_naming_tier_2_wider_radius(fake_ors):
    fake = fake_ors(_midnight_drive_trip(), reverse=lambda lat, lng, radius: "Vega" if radius == 150 else None)

    plan = _plan(start="2026-09-16T23:30")

    assert [params["boundary.circle.radius"] for params in fake.urls(geocode.REVERSE_URL)] == [25, 150]
    assert "Vega, XX" in {event.location for event in plan.events}


def test_naming_tier_3_road_near_city_chosen_by_road_mile(fake_ors):
    # Out 350 miles north and back. The rest near mile 600 is on the return leg: in a straight line it is closest
    # to the pickup (mile 50, about 50 miles away), but by road it is closest to the dropoff (mile 700).
    out = [north_of_base(mile) for mile in range(0, 351, 10)]
    back = [north_of_base(mile, BASE_LNG + 0.1) for mile in range(350, -1, -10)]
    directions = directions_payload(out + back, [[(50.0, "US-287 N")], [(300.0, "US-287 N"), (240.0, "US-287 S"), (110.0, "I-25 S")]])
    fake = fake_ors(directions, reverse=lambda lat, lng, radius: None)

    plan = _plan()

    (rest,) = [stop for stop in plan.stops if stop.kind is StopKind.REST]
    assert rest.at_mile == pytest.approx(600.0)
    assert rest.label == "I-25 S near Dropoff, CC"  # I-25 S starts at mile 590, within 25 miles of the rest
    assert len(fake.urls(geocode.REVERSE_URL)) == 2 * len({e.at_mile for e in plan.events} - {0.0, 50.0, 700.0})


def test_events_at_the_same_mile_share_one_lookup(fake_ors):
    fake = fake_ors(straight_trip(50, 700))

    plan = _plan()

    unnamed = [event for event in plan.events if event.at_mile not in {0.0, 50.0, 700.0}]
    distinct_miles = {event.at_mile for event in unnamed}
    assert len(unnamed) > len(distinct_miles)  # a rest and the drive after it start at the same mile
    assert len(fake.urls(geocode.REVERSE_URL)) == len(distinct_miles)


def test_failed_pickup_geocode_names_the_pickup(fake_ors):
    fake = fake_ors(straight_trip(55, 110))
    del fake.addresses["pickup, bb"]

    with pytest.raises(http.NotFoundError, match="pickup location"):
        _plan()
    assert fake.urls(routing.DIRECTIONS_URL) == []


@pytest.mark.parametrize(
    ("start", "tz", "expected"),
    [
        (datetime(2026, 9, 16, 0, 0, tzinfo=ZoneInfo(NEW_YORK)), NEW_YORK, 1440),
        (datetime(2026, 9, 16, 6, 0, tzinfo=ZoneInfo(NEW_YORK)), NEW_YORK, 1080),
        (datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc), NEW_YORK, 1080),  # 06:00 in New York
        (datetime(2026, 9, 16, 23, 45), NEW_YORK, 15),  # naive times are read as home-terminal time
    ],
    ids=["midnight", "six-am", "utc-input", "naive-input"],
)
def test_minutes_to_first_midnight(start, tz, expected):
    assert planner.minutes_to_first_midnight(start, tz) == expected


def test_start_time_off_the_grid_is_rejected_before_any_call(fake_ors):
    fake = fake_ors(straight_trip(55, 110))

    with pytest.raises(ValueError, match="15-minute"):
        _plan(start="2026-09-16T06:07")
    assert fake.calls == []


def test_restart_day_indices_for_exhausted_cycle(fake_ors):
    fake_ors(straight_trip(55, 110))

    plan = _plan(cycle_used_min=constants.CYCLE_LIMIT_MIN)  # 06:00 start, restart runs 06:00 to 16:00 next day

    assert plan.events[0].kind is StopKind.RESTART
    assert planner.restart_day_indices(plan.events, 1080) == frozenset({1})
    assert plan.summary.restart_required is True
    day_one = plan.sheets[1].sheet
    assert day_one.recap.a_on_duty_last_7_days == day_one.recap.on_duty_today  # prior 70 hours no longer count


def test_stop_times_are_aware_and_in_the_requested_zone(fake_ors):
    fake_ors(straight_trip(55, 110))
    chicago = "America/Chicago"

    plan = planner.plan_trip(
        "Origin, AA", "Pickup, BB", "Dropoff, CC", 0, datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc), chicago
    )

    for stop in plan.stops:
        for moment in (stop.arrive, stop.depart):
            assert moment.tzinfo is not None and moment.utcoffset() is not None
            assert moment.tzinfo.key == chicago
    assert plan.stops[0].arrive.isoformat() == "2026-09-16T06:00:00-05:00"


def test_limits_expose_every_public_integer_constant(fake_ors):
    fake_ors(straight_trip(55, 110))

    plan = _plan()

    expected = {name.lower() for name, value in vars(constants).items() if name.isupper() and type(value) is int}
    assert set(plan.limits) == expected
    assert plan.limits["drive_limit_min"] == 660
    assert plan.limits["window_limit_min"] == 840
    assert "floor_to_grid" not in plan.limits


def test_summary(fake_ors):
    fake_ors(straight_trip(100, 2000))

    plan = _plan(cycle_used_min=600)

    driving_min = sum(e.duration_min for e in plan.events if e.status is DutyStatus.DRIVING)
    work_min = sum(e.duration_min for e in plan.events if e.status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING))
    assert plan.summary.total_miles == 2000.0
    assert plan.summary.driving_hours == driving_min / 60
    assert plan.summary.elapsed_hours == plan.events[-1].end_min / 60
    assert plan.summary.days == 4
    assert plan.summary.cycle_used_at_start_hours == 10
    assert plan.summary.on_duty_added_hours == work_min / 60
    assert plan.summary.cycle_used_at_end == (600 + work_min) / 60
    assert plan.summary.restart_required is False


def test_current_location_at_pickup_routes_two_points(fake_ors):
    fake = fake_ors(straight_trip(90, 90, legs=1))
    fake.addresses["origin, aa"] = fake.addresses["pickup, bb"]  # the driver is already at the shipper

    plan = _plan()

    (body,) = [call["json"] for call in fake.requests(routing.DIRECTIONS_URL)]
    assert len(body["coordinates"]) == 2
    (pickup,) = [stop for stop in plan.stops if stop.kind is StopKind.PICKUP]
    assert pickup.at_mile == 0.0
    assert plan.events[0].kind is StopKind.PICKUP  # loading happens before any driving
    assert _kinds(plan) == [StopKind.START, StopKind.PICKUP, StopKind.DROPOFF]
