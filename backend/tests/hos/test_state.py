"""apply_event semantics, one test per numbered rule in spec §24."""
from dataclasses import replace

from trips.services.hos.enums import DutyStatus, StopKind
from trips.services.hos.events import DutyEvent
from trips.services.hos.state import DriverState, advance_day, apply_event


def _event(status, duration_min, start_min=0, kind=None):
    return DutyEvent(status=status, start_min=start_min, duration_min=duration_min, at_mile=0.0, kind=kind)


def test_rule_3_qualifying_rest_resets_and_closes_window():
    state = DriverState(
        driving_min=600, window_min=780, since_break_min=240, non_driving_run_min=0,
        miles_since_fuel=550.0, window_open=True, day_on_duty=(0, 720),
    )

    after = apply_event(state, _event(DutyStatus.SLEEPER_BERTH, 600))

    assert after.driving_min == 0
    assert after.window_min == 0
    assert after.since_break_min == 0
    assert after.window_open is False
    assert after.miles_since_fuel == 550.0
    assert after.day_on_duty == (0, 720)


def test_rule_2_and_4_short_break_clears_break_but_burns_window():
    state = DriverState(
        driving_min=480, window_min=540, since_break_min=480, non_driving_run_min=0,
        miles_since_fuel=440.0, window_open=True, day_on_duty=(0, 540),
    )

    after = apply_event(state, _event(DutyStatus.OFF_DUTY, 30))

    assert after.since_break_min == 0
    assert after.window_min == 570
    assert after.driving_min == 480
    assert after.window_open is True


def test_rule_4_and_6_pickup_clears_break_and_counts_as_work():
    state = DriverState(
        driving_min=240, window_min=240, since_break_min=240, non_driving_run_min=0,
        miles_since_fuel=220.0, window_open=True, day_on_duty=(750, 240),
    )

    after = apply_event(state, _event(DutyStatus.ON_DUTY_NOT_DRIVING, 60))

    assert after.since_break_min == 0
    assert after.window_min == 300
    assert after.cycle_min == state.cycle_min + 60
    assert after.day_on_duty == (750, 300)
    assert after.driving_min == 240


def test_rule_1_off_duty_before_work_does_not_open_window_but_driving_does():
    state = DriverState.initial(prior_cycle_min=0)

    idle = apply_event(state, _event(DutyStatus.OFF_DUTY, 60))

    assert idle.window_open is False
    assert idle.window_min == 0

    driving = apply_event(idle, _event(DutyStatus.DRIVING, 60, start_min=60))

    assert driving.window_open is True
    assert driving.window_min == 60


def test_rule_5_driving_accumulates_driving_break_window_and_miles():
    state = DriverState(
        driving_min=120, window_min=180, since_break_min=120, non_driving_run_min=0,
        miles_since_fuel=110.0, window_open=True, day_on_duty=(0, 180),
    )

    after = apply_event(state, _event(DutyStatus.DRIVING, 60))

    assert after.driving_min == 180
    assert after.since_break_min == 180
    assert after.window_min == 240
    assert after.miles_since_fuel == 165.0
    assert after.day_on_duty == (0, 240)


def test_cycle_sums_last_eight_days_and_seed_rolls_off():
    state = DriverState(
        driving_min=0, window_min=0, since_break_min=0, non_driving_run_min=0,
        miles_since_fuel=0.0, window_open=False, day_on_duty=(3000, 60, 60, 60, 60, 60, 60, 60, 60),
    )

    assert state.cycle_min == 480

    seeded = DriverState.initial(prior_cycle_min=3000)
    assert seeded.day_on_duty == (3000, 0)
    assert seeded.cycle_min == 3000

    # Day one is index 1. On day seven the seed is still inside the 8-day window.
    for _ in range(6):
        seeded = advance_day(seeded)
    assert len(seeded.day_on_duty) == 8
    assert seeded.cycle_min == 3000

    # Day eight: the window is days one to eight, so the prior hours are gone.
    seeded = advance_day(seeded)
    assert len(seeded.day_on_duty) == 9
    assert seeded.cycle_min == 0


def test_rule_6_off_duty_and_sleeper_add_nothing_to_cycle():
    state = DriverState(
        driving_min=300, window_min=360, since_break_min=0, non_driving_run_min=0,
        miles_since_fuel=275.0, window_open=True, day_on_duty=(750, 360),
    )

    after_off = apply_event(state, _event(DutyStatus.OFF_DUTY, 60))
    after_sleeper = apply_event(after_off, _event(DutyStatus.SLEEPER_BERTH, 120))

    assert after_off.day_on_duty == state.day_on_duty
    assert after_sleeper.day_on_duty == state.day_on_duty
    assert after_sleeper.cycle_min == state.cycle_min


def test_apply_event_does_not_mutate_input():
    state = DriverState(
        driving_min=300, window_min=360, since_break_min=300, non_driving_run_min=0,
        miles_since_fuel=275.0, window_open=True, day_on_duty=(750, 360),
    )
    snapshot = replace(state)

    for status in DutyStatus:
        result = apply_event(state, _event(status, 600))
        assert result is not state
        assert state == snapshot


def test_rule_7_fuel_stop_empties_fuel_counter():
    state = DriverState(
        driving_min=600, window_min=660, since_break_min=120, non_driving_run_min=0,
        miles_since_fuel=990.0, window_open=True, day_on_duty=(0, 660),
    )

    fueled = apply_event(state, _event(DutyStatus.ON_DUTY_NOT_DRIVING, 30, kind=StopKind.FUEL))
    loaded = apply_event(state, _event(DutyStatus.ON_DUTY_NOT_DRIVING, 30, kind=StopKind.PICKUP))

    assert fueled.miles_since_fuel == 0.0
    assert fueled.day_on_duty == (0, 690)
    assert loaded.miles_since_fuel == 990.0


def test_rule_8_restart_flattens_cycle_and_resets_daily_clocks():
    state = DriverState(
        driving_min=300, window_min=420, since_break_min=300, non_driving_run_min=0,
        miles_since_fuel=275.0, window_open=True, day_on_duty=(3780, 420),
    )

    restarted = apply_event(state, _event(DutyStatus.OFF_DUTY, 2040, kind=StopKind.RESTART))
    plain_rest = apply_event(state, _event(DutyStatus.OFF_DUTY, 2040))

    assert restarted.day_on_duty == (0,)
    assert restarted.cycle_min == 0
    assert (restarted.driving_min, restarted.window_min, restarted.since_break_min) == (0, 0, 0)
    assert restarted.window_open is False
    assert plain_rest.day_on_duty == (3780, 420)


def test_rule_4_split_fuel_stop_still_clears_break():
    state = DriverState(
        driving_min=420, window_min=450, since_break_min=420, non_driving_run_min=0,
        miles_since_fuel=990.0, window_open=True, day_on_duty=(0, 450),
    )

    first_half = apply_event(state, _event(DutyStatus.ON_DUTY_NOT_DRIVING, 15, kind=StopKind.FUEL))
    second_half = apply_event(first_half, _event(DutyStatus.ON_DUTY_NOT_DRIVING, 15, start_min=15, kind=StopKind.FUEL))

    assert first_half.non_driving_run_min == 15
    assert first_half.since_break_min == 420
    assert second_half.non_driving_run_min == 30
    assert second_half.since_break_min == 0


def test_rule_4_driving_breaks_the_non_driving_run():
    state = DriverState(
        driving_min=420, window_min=450, since_break_min=420, non_driving_run_min=0,
        miles_since_fuel=385.0, window_open=True, day_on_duty=(0, 450),
    )

    state = apply_event(state, _event(DutyStatus.ON_DUTY_NOT_DRIVING, 15))
    state = apply_event(state, _event(DutyStatus.DRIVING, 15, start_min=15))
    state = apply_event(state, _event(DutyStatus.OFF_DUTY, 15, start_min=30))

    assert state.non_driving_run_min == 15
    assert state.since_break_min == 435
