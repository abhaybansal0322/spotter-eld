"""Engine scenarios over handmade waypoint lists, plus invariants every plan must hold."""
import pytest

from trips.services.hos.constants import AVG_SPEED_MPH, GRID_RESOLUTION_MIN, MINUTES_PER_DAY, MINUTES_PER_HOUR
from trips.services.hos.engine import plan_duty
from trips.services.hos.enums import DutyStatus, StopKind
from trips.services.hos.events import Waypoint
from trips.services.hos.state import DriverState, advance_day, apply_event

WORK = {DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING}
REST_KINDS = {StopKind.BREAK, StopKind.REST, StopKind.RESTART}

# name: (waypoints, prior_cycle_min, minutes_to_first_midnight)
TRIPS = {
    "eleven_hour": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(700, StopKind.DROPOFF, "B", 60)),
        0, 1080,
    ),
    "long_pickup": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(110, StopKind.PICKUP, "P", 360),
         Waypoint(700, StopKind.DROPOFF, "B", 60)),
        0, 1080,
    ),
    "pickup_break": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(330, StopKind.PICKUP, "P", 60),
         Waypoint(550, StopKind.DROPOFF, "B", 60)),
        0, 1080,
    ),
    "cycle_exhausted": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(55, StopKind.PICKUP, "P", 60),
         Waypoint(110, StopKind.DROPOFF, "B", 60)),
        4200, 1080,
    ),
    "multi_day": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(100, StopKind.PICKUP, "P", 60),
         Waypoint(2000, StopKind.DROPOFF, "B", 60)),
        600, 1080,
    ),
    "short_from_midnight": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(55, StopKind.PICKUP, "P", 60),
         Waypoint(110, StopKind.DROPOFF, "B", 60)),
        0, 1440,
    ),
    "pickup_across_midnight": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(55, StopKind.PICKUP, "P", 60),
         Waypoint(110, StopKind.DROPOFF, "B", 60)),
        0, 90,
    ),
    "fuel_across_midnight": (
        (Waypoint(0, StopKind.START, "A", 0), Waypoint(100, StopKind.PICKUP, "P", 60),
         Waypoint(2000, StopKind.DROPOFF, "B", 60)),
        600, 345,
    ),
}


def _plan(name):
    waypoints, prior, midnight = TRIPS[name]
    return plan_duty(waypoints, DriverState.initial(prior), midnight)


def _driving_before(events, index):
    return sum(e.duration_min for e in events[:index] if e.status is DutyStatus.DRIVING)


def _first(events, kind):
    return next(i for i, e in enumerate(events) if e.kind is kind)


# Scenarios


def test_scenario_1_eleven_hour_limit_binds_before_window():
    events = _plan("eleven_hour")
    rest = _first(events, StopKind.REST)

    assert events[rest].status is DutyStatus.SLEEPER_BERTH
    assert events[rest].duration_min == 600
    assert _driving_before(events, rest) == 660
    assert events[rest].start_min - events[0].start_min == 690  # window still under 840
    assert [e.kind for e in events[:rest] if e.kind is StopKind.BREAK] == [StopKind.BREAK]


def test_scenario_2_window_binds_before_eleven_hours_because_of_long_pickup():
    events = _plan("long_pickup")
    rest = _first(events, StopKind.REST)

    assert events[rest].status is DutyStatus.SLEEPER_BERTH
    assert events[rest].start_min - events[0].start_min == 840
    assert _driving_before(events, rest) == 480  # under 660


def test_scenario_3_pickup_satisfies_break():
    events = _plan("pickup_break")

    assert all(e.kind is not StopKind.BREAK for e in events)
    assert sum(e.duration_min for e in events if e.status is DutyStatus.DRIVING) > 480


def test_scenario_4_exhausted_cycle_forces_restart_before_driving():
    events = _plan("cycle_exhausted")
    first_drive = next(i for i, e in enumerate(events) if e.status is DutyStatus.DRIVING)
    restart = events[first_drive - 1]

    assert first_drive == 1
    assert restart.kind is StopKind.RESTART
    assert restart.status is DutyStatus.OFF_DUTY
    assert restart.duration_min == 2040


def test_scenario_5_multi_day_fuel_and_cycle():
    waypoints, prior, midnight = TRIPS["multi_day"]
    initial = DriverState.initial(prior)
    events = plan_duty(waypoints, initial, midnight)

    fuel = [i for i, e in enumerate(events) if e.kind is StopKind.FUEL]
    assert [events[i].at_mile for i in fuel] == [980.0, 1970.0]
    previous = 0
    for i in fuel:
        derived_miles = (_driving_before(events, i) - _driving_before(events, previous)) / MINUTES_PER_HOUR * AVG_SPEED_MPH
        assert 1000 - GRID_RESOLUTION_MIN / MINUTES_PER_HOUR * AVG_SPEED_MPH < derived_miles <= 1000
        previous = i

    state, next_midnight = initial, midnight
    for event in events:
        state = apply_event(state, event)
        while event.end_min >= next_midnight:
            state = advance_day(state)
            next_midnight += MINUTES_PER_DAY
    assert state.day_on_duty == (600, 720, 690, 690, 285)  # prior seed, then four calendar days
    assert state.cycle_min == 600 + sum(e.duration_min for e in events if e.status in WORK)


# Invariants, over every trip

ALL_TRIPS = pytest.mark.parametrize("name", list(TRIPS))


@ALL_TRIPS
def test_invariant_6_durations_are_grid_multiples(name):
    assert all(e.duration_min % GRID_RESOLUTION_MIN == 0 for e in _plan(name))


@ALL_TRIPS
def test_invariant_7_events_are_contiguous_from_zero(name):
    events = _plan(name)

    assert events[0].start_min == 0
    for previous, current in zip(events, events[1:]):
        assert current.start_min == previous.end_min


@ALL_TRIPS
def test_invariant_8_work_never_crosses_midnight(name):
    _, _, midnight = TRIPS[name]

    def day(minute):
        return (minute - midnight) // MINUTES_PER_DAY

    for event in _plan(name):
        if event.status in WORK:
            assert day(event.start_min) == day(event.end_min - 1), event


@ALL_TRIPS
def test_invariant_9_nothing_follows_final_waypoint(name):
    waypoints, _, _ = TRIPS[name]
    events = _plan(name)
    arrival = _first(events, waypoints[-1].kind)

    assert all(e.kind is waypoints[-1].kind and e.status is DutyStatus.ON_DUTY_NOT_DRIVING for e in events[arrival:])
    assert events[-1].end_min - events[arrival].start_min == waypoints[-1].duration_min


def test_invariant_10_short_trip_has_no_rests():
    events = _plan("short_from_midnight")

    assert all(e.status in WORK for e in events)
    assert all(e.kind not in REST_KINDS for e in events)


@ALL_TRIPS
def test_invariant_11_driving_covers_route_distance(name):
    waypoints, _, _ = TRIPS[name]
    driven_miles = sum(
        e.duration_min for e in _plan(name) if e.status is DutyStatus.DRIVING
    ) / MINUTES_PER_HOUR * AVG_SPEED_MPH
    legs = len(waypoints) - 1
    grid_miles = GRID_RESOLUTION_MIN / MINUTES_PER_HOUR * AVG_SPEED_MPH

    assert waypoints[-1].at_mile <= driven_miles < waypoints[-1].at_mile + legs * grid_miles


def test_waypoint_work_across_midnight_is_split():
    events = _plan("pickup_across_midnight")
    pickups = [e for e in events if e.kind is StopKind.PICKUP]

    assert [(e.start_min, e.duration_min) for e in pickups] == [(60, 30), (90, 30)]


def test_fuel_stop_split_at_midnight_does_not_add_a_break():
    split = _plan("fuel_across_midnight")
    whole = _plan("multi_day")

    fuel = [e for e in split if e.kind is StopKind.FUEL]
    assert [(e.start_min, e.duration_min) for e in fuel[:2]] == [(1770, 15), (1785, 15)]
    assert sum(e.kind is StopKind.BREAK for e in split) == sum(e.kind is StopKind.BREAK for e in whole)
    assert split[-1].end_min == whole[-1].end_min


# Input validation


@pytest.mark.parametrize("midnight", [0, -15, 1441])
def test_rejects_minutes_to_first_midnight_out_of_range(midnight):
    waypoints, prior, _ = TRIPS["short_from_midnight"]

    with pytest.raises(ValueError, match="minutes_to_first_midnight"):
        plan_duty(waypoints, DriverState.initial(prior), midnight)


def test_rejects_decreasing_waypoint_miles():
    waypoints = (Waypoint(0, StopKind.START, "A", 0), Waypoint(110, StopKind.PICKUP, "P", 60),
                 Waypoint(55, StopKind.DROPOFF, "B", 60))

    with pytest.raises(ValueError, match="non-decreasing"):
        plan_duty(waypoints, DriverState.initial(0), 1080)


def test_rejects_negative_first_mile():
    waypoints = (Waypoint(-5, StopKind.START, "A", 0), Waypoint(55, StopKind.DROPOFF, "B", 60))

    with pytest.raises(ValueError, match="non-negative"):
        plan_duty(waypoints, DriverState.initial(0), 1080)
