"""Each rule in isolation against a hand-built DriverState."""
from dataclasses import replace

import pytest

from trips.services.hos.enums import DutyStatus, StopKind
from trips.services.hos.events import RestRequirement
from trips.services.hos.rules import (
    RULES,
    AdverseDrivingRule,
    ElevenHourRule,
    FourteenHourWindowRule,
    FuelStopRule,
    SeventyHourCycleRule,
    ShortHaulRule,
    SixtyHourCycleRule,
    SplitSleeperBerthRule,
    ThirtyMinuteBreakRule,
)
from trips.services.hos.state import DriverState

FRESH = DriverState(
    driving_min=0, window_min=0, since_break_min=0, non_driving_run_min=0,
    miles_since_fuel=0.0, window_open=False, day_on_duty=(0, 0),
)


@pytest.mark.parametrize(
    ("rule", "state", "expected"),
    [
        (SeventyHourCycleRule(), replace(FRESH, day_on_duty=(4185, 0)), 15),
        (SeventyHourCycleRule(), replace(FRESH, day_on_duty=(4200, 0)), 0),
        (SeventyHourCycleRule(), replace(FRESH, day_on_duty=(3600, 700)), 0),
        (FourteenHourWindowRule(), replace(FRESH, window_min=825, window_open=True), 15),
        (FourteenHourWindowRule(), replace(FRESH, window_min=840, window_open=True), 0),
        (FourteenHourWindowRule(), replace(FRESH, window_min=900, window_open=True), 0),
        (ElevenHourRule(), replace(FRESH, driving_min=645), 15),
        (ElevenHourRule(), replace(FRESH, driving_min=660), 0),
        (ElevenHourRule(), replace(FRESH, driving_min=700), 0),
        (ThirtyMinuteBreakRule(), replace(FRESH, since_break_min=465), 15),
        (ThirtyMinuteBreakRule(), replace(FRESH, since_break_min=480), 0),
        (ThirtyMinuteBreakRule(), replace(FRESH, since_break_min=510), 0),
        (FuelStopRule(), FRESH, 1090),
        (FuelStopRule(), replace(FRESH, miles_since_fuel=986.25), 15),
        (FuelStopRule(), replace(FRESH, miles_since_fuel=1000.0), 0),
        (FuelStopRule(), replace(FRESH, miles_since_fuel=1100.0), 0),
    ],
    ids=[
        "cycle-4185", "cycle-4200", "cycle-overshoot",
        "window-825", "window-840", "window-overshoot",
        "driving-645", "driving-660", "driving-overshoot",
        "break-465", "break-480", "break-overshoot",
        "fuel-fresh", "fuel-986.25mi", "fuel-1000mi", "fuel-overshoot",
    ],
)
def test_driving_allowance_boundaries_and_never_negative(rule, state, expected):
    allowance = rule.driving_allowance(state)

    assert allowance == expected
    assert type(allowance) is int


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (SeventyHourCycleRule(), RestRequirement(DutyStatus.OFF_DUTY, 2040, StopKind.RESTART)),
        (FourteenHourWindowRule(), RestRequirement(DutyStatus.SLEEPER_BERTH, 600, StopKind.REST)),
        (ElevenHourRule(), RestRequirement(DutyStatus.SLEEPER_BERTH, 600, StopKind.REST)),
        (ThirtyMinuteBreakRule(), RestRequirement(DutyStatus.OFF_DUTY, 30, StopKind.BREAK)),
        (FuelStopRule(), RestRequirement(DutyStatus.ON_DUTY_NOT_DRIVING, 30, StopKind.FUEL)),
    ],
    ids=["cycle", "window", "eleven", "break", "fuel"],
)
def test_rest_requirement_matches_spec_table(rule, expected):
    assert rule.rest_requirement() == expected


@pytest.mark.parametrize(
    "rule",
    [AdverseDrivingRule(), SplitSleeperBerthRule(), ShortHaulRule(), SixtyHourCycleRule()],
    ids=lambda rule: type(rule).__name__,
)
def test_placeholder_rules_are_not_implemented(rule):
    with pytest.raises(NotImplementedError):
        rule.driving_allowance(FRESH)
    with pytest.raises(NotImplementedError):
        rule.rest_requirement()


def test_rules_tuple_order_is_the_tie_break_order():
    assert [type(rule) for rule in RULES] == [
        SeventyHourCycleRule,
        FourteenHourWindowRule,
        ElevenHourRule,
        ThirtyMinuteBreakRule,
        FuelStopRule,
    ]
