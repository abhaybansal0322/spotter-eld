"""DaySheet assembly, including the FMCSA John Doe reference log from page 18 of the guide."""
import pytest

from trips.services.hos.constants import MINUTES_PER_DAY
from trips.services.hos.engine import plan_duty
from trips.services.hos.enums import DutyStatus, StopKind
from trips.services.hos.events import DutyEvent, Waypoint
from trips.services.hos.segments import split_at_midnight
from trips.services.hos.sheets import build_sheets
from trips.services.hos.state import DriverState

OFF, SB, DRIVE, ON = DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH, DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING


def _event(status, start_min, duration_min, **fields):
    return DutyEvent(status=status, start_min=start_min, duration_min=duration_min, at_mile=fields.pop("at_mile", 0.0), **fields)


def _sheets(events, minutes_to_first_midnight, prior_cycle_min=0, restart_day_indices=frozenset()):
    sheets = build_sheets(
        split_at_midnight(events, minutes_to_first_midnight), minutes_to_first_midnight, prior_cycle_min, restart_day_indices
    )
    for sheet in sheets:
        _assert_full_day(sheet)
    return sheets


def _assert_full_day(sheet):
    assert sheet.totals[OFF] + sheet.totals[SB] + sheet.totals[DRIVE] + sheet.totals[ON] == MINUTES_PER_DAY
    assert sheet.segments[0][1] == 0
    assert sheet.segments[-1][2] == MINUTES_PER_DAY
    for (_, _, end), (_, start, _) in zip(sheet.segments, sheet.segments[1:]):
        assert start == end


# John Doe, Richmond VA to Newark NJ. Trip minute 0 is his 6:00 a.m. report time, so midnight is 1080 minutes away.
JOHN_DOE_MIDNIGHT = 1080
JOHN_DOE = [
    _event(ON, 0, 90, location="Richmond, VA", at_mile=0.0),  # 6:00 load, dispatch, pre-trip
    _event(DRIVE, 90, 90, location="Richmond, VA", at_mile=0.0),  # 7:30
    _event(ON, 180, 30, kind=StopKind.FUEL, location="Fredericksburg, VA", at_mile=82.5),  # 9:00 fuel
    _event(DRIVE, 210, 150, location="Fredericksburg, VA", at_mile=82.5),  # 9:30
    _event(OFF, 360, 60, location="Baltimore, MD", at_mile=220.0),  # 12:00 lunch
    _event(DRIVE, 420, 120, location="Baltimore, MD", at_mile=220.0),  # 1:00 p.m.
    _event(ON, 540, 30, kind=StopKind.DROPOFF, location="Philadelphia, PA", at_mile=330.0),  # 3:00 delivery
    _event(DRIVE, 570, 30, location="Philadelphia, PA", at_mile=330.0),  # 3:30
    _event(SB, 600, 105, location="Cherry Hill, NJ", at_mile=357.5),  # 4:00 sleeper
    _event(DRIVE, 705, 75, location="Cherry Hill, NJ", at_mile=357.5),  # 5:45
    _event(ON, 780, 120, location="Newark, NJ", at_mile=426.25),  # 7:00 post-trip, paperwork, off at 9:00
]


def test_john_doe_reference_log():
    (sheet,) = _sheets(JOHN_DOE, JOHN_DOE_MIDNIGHT)

    assert sheet.totals == {OFF: 600, SB: 105, DRIVE: 465, ON: 270}
    assert sheet.total_miles_driving == 426.25
    assert sheet.segments[0] == (OFF, 0, 360)
    assert sheet.segments[-1] == (OFF, 1260, 1440)

    # Page 18: twelve status changes, six places, six labels.
    assert sheet.remarks == (
        (360, "Richmond, VA"),
        (540, "Fredericksburg, VA"),
        (720, "Baltimore, MD"),
        (900, "Philadelphia, PA"),
        (960, "Cherry Hill, NJ"),
        (1140, "Newark, NJ"),
    )


# Starts 6:00 a.m., sleeps across midnight, finishes 4:00 a.m. on day two.
TWO_DAY = [
    _event(ON, 0, 60, location="Richmond, VA"),
    _event(DRIVE, 60, 540, location="Richmond, VA"),
    _event(SB, 600, 600, location="Savannah, GA"),
    _event(DRIVE, 1200, 120, location="Savannah, GA"),
]


def test_leading_padding_on_first_day():
    first, _ = _sheets(TWO_DAY, 1080)

    assert first.segments[0] == (OFF, 0, 360)
    assert first.segments[1] == (ON, 360, 420)
    assert first.segments[-1] == (SB, 960, 1440)


def test_trailing_padding_on_final_day():
    _, last = _sheets(TWO_DAY, 1080)

    assert last.segments[0] == (SB, 0, 120)
    assert last.segments[-1] == (OFF, 240, 1440)


def test_day_inside_one_rest_is_a_full_day_of_that_status():
    events = [
        _event(DRIVE, 0, 60, location="Harrisburg, PA"),
        _event(OFF, 60, 2040, kind=StopKind.RESTART, location="Carlisle, PA"),
        _event(DRIVE, 2100, 60, location="Carlisle, PA"),
    ]

    _, middle, _ = _sheets(events, 120)

    assert middle.segments == ((OFF, 0, MINUTES_PER_DAY),)
    assert middle.totals[OFF] == MINUTES_PER_DAY
    assert middle.remarks == ((0, "Carlisle, PA"),)
    assert middle.total_miles_driving == 0


def test_multi_day_engine_output_every_sheet_is_a_full_day():
    waypoints = (Waypoint(0, StopKind.START, "A", 0), Waypoint(100, StopKind.PICKUP, "P", 60),
                 Waypoint(2000, StopKind.DROPOFF, "B", 60))
    events = plan_duty(waypoints, DriverState.initial(600), 345)

    sheets = _sheets(events, 345, prior_cycle_min=600)  # no restart on this trip

    assert [sheet.date_index for sheet in sheets] == [0, 1, 2, 3]
    assert sum(s.totals[DRIVE] + s.totals[ON] for s in sheets) == sum(
        e.duration_min for e in events if e.status in (DRIVE, ON)
    )


def _daily_on_duty(minutes_per_day):
    """One day per entry, starting at midnight: on duty first, off duty for the rest of the day."""
    events = []
    for day, on_minutes in enumerate(minutes_per_day):
        start = day * MINUTES_PER_DAY
        events.append(_event(ON, start, on_minutes))
        events.append(_event(OFF, start + on_minutes, MINUTES_PER_DAY - on_minutes))
    return events


def test_recap_boxes_with_prior_cycle_hours():
    sheets = _sheets(_daily_on_duty([600, 480, 300, 300, 300, 300, 300]), 1440, prior_cycle_min=1800)
    recaps = [sheet.recap for sheet in sheets]

    # Day 1: both windows still reach before the trip, so the 1800 prior minutes count in A and C.
    assert recaps[1].on_duty_today == 480
    assert recaps[1].a_on_duty_last_7_days == 600 + 480 + 1800
    assert recaps[1].b_available_tomorrow == 4200 - 2880
    assert recaps[1].c_on_duty_last_5_days == 600 + 480 + 1800

    # Day 4: C covers days 0-4 only, so prior hours are out of C but still in A.
    assert recaps[4].a_on_duty_last_7_days == 600 + 480 + 900 + 1800
    assert recaps[4].b_available_tomorrow == 420
    assert recaps[4].c_on_duty_last_5_days == 600 + 480 + 900

    # Day 6: A covers days 0-6, so prior hours are out of A too.
    assert recaps[6].a_on_duty_last_7_days == 600 + 480 + 1500
    assert recaps[6].b_available_tomorrow == 4200 - 2580
    assert recaps[6].c_on_duty_last_5_days == 1500


def test_recap_b_never_negative():
    sheets = _sheets(_daily_on_duty([840, 840]), 1440, prior_cycle_min=4200)

    assert [sheet.recap.a_on_duty_last_7_days for sheet in sheets] == [5040, 5880]
    assert all(sheet.recap.b_available_tomorrow == 0 for sheet in sheets)


def test_remarks_only_at_status_changes_and_only_when_the_place_changes():
    events = [
        _event(DRIVE, 0, 120, location="Richmond, VA"),
        _event(ON, 120, 60, kind=StopKind.PICKUP, location="Baltimore, MD"),
        _event(ON, 180, 30, kind=StopKind.FUEL, location="Baltimore, MD"),  # same status, no remark
        _event(DRIVE, 210, 60, location="Baltimore, MD"),
        _event(DRIVE, 270, 60, location="Wilmington, DE"),  # same status, no remark
        _event(OFF, 330, 30, kind=StopKind.BREAK, location="Newark, DE"),
        _event(DRIVE, 360, 90, location="Newark, DE"),
        _event(ON, 450, 60, kind=StopKind.DROPOFF, location="Newark, NJ"),
    ]

    (sheet,) = _sheets(events, 1080)

    change_minutes = {start for _, start, _ in sheet.segments[1:]}
    assert all(at_min in change_minutes for at_min, _ in sheet.remarks)
    assert all(a[1] != b[1] for a, b in zip(sheet.remarks, sheet.remarks[1:]))
    # Seven status changes; Baltimore, Newark DE and Newark NJ are each entered and left, so four remarks.
    assert len(change_minutes) == 7
    assert sheet.remarks == (
        (360, "Richmond, VA"), (480, "Baltimore, MD"), (690, "Newark, DE"), (810, "Newark, NJ"),
    )


def test_midnight_remark_on_every_day_after_the_first():
    first, second = _sheets(TWO_DAY, 1080)

    assert first.remarks == ((360, "Richmond, VA"), (960, "Savannah, GA"))
    assert all(at_min != 0 for at_min, _ in first.remarks)
    # Day two opens mid-sleep in Savannah; the drive and the release there repeat the place, so nothing else.
    assert second.remarks == ((0, "Savannah, GA"),)


def _restart_trip():
    """Days 0-2 work 600 minutes each, a 38-hour restart covers all of day 3, day 4 works 480."""
    events = []
    for day in range(3):
        start = day * MINUTES_PER_DAY
        events.append(_event(ON, start, 600))
        if day < 2:
            events.append(_event(OFF, start + 600, 840))
    events.append(_event(OFF, 2 * MINUTES_PER_DAY + 600, 2280, kind=StopKind.RESTART))
    events.append(_event(ON, 4 * MINUTES_PER_DAY, 480))
    events.append(_event(OFF, 4 * MINUTES_PER_DAY + 480, 960))
    return events


def test_recap_restart_cuts_the_window():
    sheets = _sheets(_restart_trip(), 1440, prior_cycle_min=1800, restart_day_indices=frozenset({3}))
    recaps = [sheet.recap for sheet in sheets]

    assert [sheet.recap.on_duty_today for sheet in sheets] == [600, 600, 600, 0, 480]
    assert recaps[2].a_on_duty_last_7_days == 1800 + 1800  # before the restart, prior hours still count
    assert recaps[3].a_on_duty_last_7_days == 0
    assert recaps[4].a_on_duty_last_7_days == 480
    assert recaps[4].b_available_tomorrow == 4200 - 480
    assert recaps[4].c_on_duty_last_5_days == 480


def test_recap_empty_restart_set_is_unchanged():
    events = _daily_on_duty([600, 480, 300, 300, 300, 300, 300])

    no_restart = _sheets(events, 1440, prior_cycle_min=1800, restart_day_indices=frozenset())
    restart_after_trip = _sheets(events, 1440, prior_cycle_min=1800, restart_day_indices=frozenset({7}))

    assert [s.recap for s in no_restart] == [s.recap for s in restart_after_trip]
    assert [s.recap.a_on_duty_last_7_days for s in no_restart] == [2400, 2880, 3180, 3480, 3780, 4080, 2580]


def test_trip_starting_at_midnight_logs_start_location_on_day_zero():
    events = [
        _event(ON, 0, 60, location="Richmond, VA"),
        _event(DRIVE, 60, 120, location="Richmond, VA"),
        _event(ON, 180, 60, kind=StopKind.DROPOFF, location="Fredericksburg, VA"),
    ]

    (sheet,) = _sheets(events, 1440)

    assert sheet.segments[0] == (ON, 0, 60)
    assert sheet.remarks == ((0, "Richmond, VA"), (180, "Fredericksburg, VA"))


def test_day_miles_come_from_positions_not_minutes_at_55_mph():
    # Amarillo to Dumas to Denver, live: 48.1 and 374.1 road miles. Each leg's driving time rounds up to the grid
    # (60 and 420 minutes), so minutes at 55 mph would claim 440 miles for a 422.2-mile route.
    waypoints = (Waypoint(0.0, StopKind.START, "Amarillo, TX", 0), Waypoint(48.1, StopKind.PICKUP, "Dumas, TX", 60),
                 Waypoint(422.2, StopKind.DROPOFF, "Denver, CO", 60))
    events = plan_duty(waypoints, DriverState.initial(0), 1080)

    (sheet,) = _sheets(events, 1080)

    assert sheet.totals[DRIVE] == 480
    assert sheet.total_miles_driving == pytest.approx(422.2)


def test_multi_day_sheets_add_up_to_the_route_distance():
    waypoints = (Waypoint(0.0, StopKind.START, "A", 0), Waypoint(97.3, StopKind.PICKUP, "P", 60),
                 Waypoint(2004.6, StopKind.DROPOFF, "B", 60))
    events = plan_duty(waypoints, DriverState.initial(600), 345)

    sheets = _sheets(events, 345)

    assert len(sheets) >= 3
    assert sum(sheet.total_miles_driving for sheet in sheets) == pytest.approx(2004.6, abs=1e-9)
    assert all(sheet.total_miles_driving >= 0 for sheet in sheets)
    # A day of driving never claims more than its minutes allow at 55 mph: positions only ever remove the rounding.
    assert all(sheet.total_miles_driving <= sheet.totals[DRIVE] * 55 / 60 + 1e-9 for sheet in sheets)


def test_a_drive_cut_at_midnight_shares_its_miles_by_minutes():
    events = [
        _event(DRIVE, 0, 120, location="A", at_mile=0.0),  # 22:00 to 00:00, then on past midnight
        _event(DRIVE, 120, 60, location="A", at_mile=0.0),
        _event(ON, 180, 60, kind=StopKind.DROPOFF, location="B", at_mile=150.0),
    ]

    first, second = _sheets(events, 120)

    assert (first.total_miles_driving, second.total_miles_driving) == (100.0, 50.0)
