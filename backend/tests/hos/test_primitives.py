"""Enums, events and grid rounding."""
import pytest

from trips.services.hos.constants import ceil_to_grid, floor_to_grid
from trips.services.hos.enums import DutyStatus, StopKind
from trips.services.hos.events import DutyEvent


def test_duty_status_row_indices_follow_form_order():
    assert [status.row_index for status in DutyStatus] == [0, 1, 2, 3]
    assert list(DutyStatus) == [
        DutyStatus.OFF_DUTY,
        DutyStatus.SLEEPER_BERTH,
        DutyStatus.DRIVING,
        DutyStatus.ON_DUTY_NOT_DRIVING,
    ]


def test_only_driving_is_driving():
    assert [status for status in DutyStatus if status.is_driving] == [DutyStatus.DRIVING]


def test_stop_kind_values_are_api_strings():
    assert [kind.value for kind in StopKind] == [
        "START", "PICKUP", "DROPOFF", "FUEL", "BREAK", "REST", "RESTART",
    ]


@pytest.mark.parametrize(
    ("start_min", "duration_min"),
    [(0, 0), (-15, 30), (0, 20), (10, 30)],
    ids=["zero-duration", "negative-start", "duration-off-grid", "start-off-grid"],
)
def test_duty_event_rejects_invalid_times(start_min, duration_min):
    with pytest.raises(ValueError):
        DutyEvent(status=DutyStatus.DRIVING, start_min=start_min, duration_min=duration_min, at_mile=0.0)


def test_duty_event_end_min():
    event = DutyEvent(status=DutyStatus.ON_DUTY_NOT_DRIVING, start_min=90, duration_min=60, at_mile=12.5)

    assert event.end_min == 150
    assert event.kind is None
    assert event.location is None
    assert event.remark is None


@pytest.mark.parametrize(
    ("minutes", "floored", "ceiled"),
    [(0, 0, 0), (1, 0, 15), (14, 0, 15), (15, 15, 15), (16, 15, 30), (29, 15, 30), (30, 30, 30)],
)
def test_grid_rounding(minutes, floored, ceiled):
    assert floor_to_grid(minutes) == floored
    assert ceil_to_grid(minutes) == ceiled
    assert type(floor_to_grid(minutes)) is int
    assert type(ceil_to_grid(minutes)) is int
