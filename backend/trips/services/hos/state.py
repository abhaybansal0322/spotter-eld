"""DriverState accumulators and the pure apply_event function (spec §24)."""
from dataclasses import dataclass, replace

from .constants import AVG_SPEED_MPH, BREAK_QUALIFY_MIN, CYCLE_DAYS, MINUTES_PER_DAY, MINUTES_PER_HOUR, QUALIFYING_REST_MIN
from .enums import DutyStatus, StopKind

_WORK = frozenset({DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING})


@dataclass(frozen=True)
class DriverState:
    """Accumulators only. No decision-making lives here."""

    driving_min: int
    window_min: int
    since_break_min: int
    non_driving_run_min: int
    miles_since_fuel: float
    window_open: bool
    day_on_duty: tuple[int, ...]

    @property
    def cycle_min(self):
        return sum(self.day_on_duty[-CYCLE_DAYS:])

    @classmethod
    def initial(cls, prior_cycle_min):
        """Fresh off a 10-hour rest. Prior cycle hours are one synthetic day, followed by trip day one."""
        return cls(
            driving_min=0,
            window_min=0,
            since_break_min=0,
            non_driving_run_min=0,
            miles_since_fuel=0.0,
            window_open=False,
            day_on_duty=(prior_cycle_min, 0),
        )


def apply_event(state, event):
    """Return the state after event. Rules 1-8 of spec §24, in order."""
    duration = event.duration_min
    is_work = event.status in _WORK

    # 1. Window opening: only work opens the window.
    window_open = state.window_open or is_work

    # 2. Window accumulation: once open, every event counts, breaks and meals included.
    window_min = state.window_min + duration if window_open else state.window_min

    driving_min = state.driving_min
    since_break_min = state.since_break_min

    # 3. Qualifying rest: zeroes driving, window and break, and closes the window.
    if not is_work and duration >= QUALIFYING_REST_MIN:
        driving_min = window_min = since_break_min = 0
        window_open = False

    # 4. Break satisfaction: consecutive non-driving time accrues across events, so 15 on duty plus
    #    15 off, or a fuel stop cut in half at midnight, still clears the break clock.
    non_driving_run_min = 0 if event.status.is_driving else state.non_driving_run_min + duration
    if non_driving_run_min >= BREAK_QUALIFY_MIN:
        since_break_min = 0

    # 5. Driving: mileage is derived from duration, never carried on the event.
    miles_since_fuel = state.miles_since_fuel
    if event.status.is_driving:
        driving_min += duration
        since_break_min += duration
        miles_since_fuel += duration / MINUTES_PER_HOUR * AVG_SPEED_MPH

    # 6. Cycle: on-duty time lands on the current day.
    day_on_duty = state.day_on_duty
    if is_work:
        day_on_duty = (*day_on_duty[:-1], day_on_duty[-1] + duration)

    # 7. Fuel: a fuel stop empties the fuel counter.
    if event.kind is StopKind.FUEL:
        miles_since_fuel = 0.0

    # 8. Restart: 34 hours off flattens the cycle; rule 3 already reset the daily clocks.
    if event.kind is StopKind.RESTART:
        day_on_duty = (0,)

    return replace(
        state,
        driving_min=driving_min,
        window_min=window_min,
        since_break_min=since_break_min,
        non_driving_run_min=non_driving_run_min,
        miles_since_fuel=miles_since_fuel,
        window_open=window_open,
        day_on_duty=day_on_duty,
    )


def advance_day(state):
    """Open a new calendar day in the cycle ledger."""
    return replace(state, day_on_duty=(*state.day_on_duty, 0))


def replay(events, initial_state, minutes_to_first_midnight):
    """Fold a finished, contiguous event list back through apply_event and advance_day, giving the end state."""
    state, next_midnight = initial_state, minutes_to_first_midnight
    for event in events:
        state = apply_event(state, event)
        while event.end_min >= next_midnight:
            state = advance_day(state)
            next_midnight += MINUTES_PER_DAY
    return state
