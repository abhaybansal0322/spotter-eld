"""Midnight splitting over hand-built event lists."""
import pytest

from trips.services.hos.constants import MINUTES_PER_DAY
from trips.services.hos.enums import DutyStatus, StopKind
from trips.services.hos.events import DutyEvent
from trips.services.hos.segments import split_at_midnight

OFF, SB, DRIVE, ON = DutyStatus.OFF_DUTY, DutyStatus.SLEEPER_BERTH, DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING


def _event(status, start_min, duration_min, **fields):
    return DutyEvent(status=status, start_min=start_min, duration_min=duration_min, at_mile=fields.pop("at_mile", 0.0), **fields)


def _assert_contiguous(buckets, minutes_to_first_midnight):
    flat = [event for bucket in buckets for event in bucket]
    for previous, current in zip(flat, flat[1:]):
        assert current.start_min == previous.end_min
    for index, bucket in enumerate(buckets):
        day_end = minutes_to_first_midnight + index * MINUTES_PER_DAY
        for event in bucket:
            assert day_end - MINUTES_PER_DAY <= event.start_min < event.end_min <= day_end


def test_trip_inside_one_day_is_one_bucket():
    events = [_event(ON, 0, 60), _event(DRIVE, 60, 120), _event(ON, 180, 60)]

    buckets = split_at_midnight(events, 1080)

    assert buckets == [events]
    _assert_contiguous(buckets, 1080)


def test_straddling_event_is_cut_and_halves_sum_to_original():
    rest = _event(SB, 60, 600)

    buckets = split_at_midnight([_event(DRIVE, 0, 60), rest], 120)

    first, second = buckets[0][-1], buckets[1][0]
    assert (first.start_min, first.duration_min) == (60, 60)
    assert (second.start_min, second.duration_min) == (120, 540)
    assert first.duration_min + second.duration_min == rest.duration_min
    _assert_contiguous(buckets, 120)


def test_second_half_keeps_status_kind_location_and_mile():
    fuel = _event(ON, 90, 30, kind=StopKind.FUEL, location="Fredericksburg, VA", at_mile=82.5, remark="fueled")

    buckets = split_at_midnight([_event(DRIVE, 0, 90), fuel], 105)

    second = buckets[1][0]
    assert second.status is ON
    assert second.kind is StopKind.FUEL
    assert second.location == "Fredericksburg, VA"
    assert second.at_mile == 82.5
    assert second.remark == "fueled"


@pytest.mark.parametrize(
    ("rest", "expected_days"),
    [
        (_event(OFF, 60, 2040, kind=StopKind.RESTART), 3),  # 34h can span at most two midnights
        (_event(OFF, 60, 3600), 4),  # a 60h rest spans three
    ],
    ids=["34h-restart", "60h-rest"],
)
def test_long_rest_yields_contiguous_day_buckets(rest, expected_days):
    events = [_event(DRIVE, 0, 60), rest, _event(DRIVE, rest.end_min, 60)]

    buckets = split_at_midnight(events, 120)

    assert len(buckets) == expected_days
    assert all(bucket for bucket in buckets)
    for middle in buckets[1:-1]:
        assert [(e.status, e.duration_min) for e in middle] == [(OFF, MINUTES_PER_DAY)]
    assert sum(e.duration_min for bucket in buckets for e in bucket if e.status is OFF) == rest.duration_min
    _assert_contiguous(buckets, 120)


def test_trip_starting_at_midnight_puts_first_event_in_bucket_zero():
    events = [_event(DRIVE, 0, 1380), _event(ON, 1380, 60), _event(DRIVE, 1440, 60)]

    buckets = split_at_midnight(events, 1440)

    assert [len(bucket) for bucket in buckets] == [2, 1]
    assert buckets[0][0] == events[0]
    _assert_contiguous(buckets, 1440)


def test_every_bucket_is_contiguous_and_ordered():
    events = [
        _event(DRIVE, 0, 480), _event(OFF, 480, 30, kind=StopKind.BREAK), _event(DRIVE, 510, 180),
        _event(SB, 690, 600, kind=StopKind.REST), _event(DRIVE, 1290, 420),
        _event(ON, 1710, 30, kind=StopKind.FUEL), _event(DRIVE, 1740, 240),
        _event(SB, 1980, 600, kind=StopKind.REST), _event(DRIVE, 2580, 105), _event(ON, 2685, 60),
    ]

    buckets = split_at_midnight(events, 345)

    assert len(buckets) == 3
    for bucket in buckets:
        assert [e.start_min for e in bucket] == sorted(e.start_min for e in bucket)
    _assert_contiguous(buckets, 345)


def test_rejects_minutes_to_first_midnight_out_of_range():
    with pytest.raises(ValueError):
        split_at_midnight([_event(DRIVE, 0, 60)], 0)
