"""The plan_duty loop that turns waypoints into duty events."""
from .constants import (
    AVG_SPEED_MPH,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    ceil_to_grid,
    floor_to_grid,
)
from .enums import DutyStatus
from .events import DutyEvent
from .rules import RULES
from .state import advance_day, apply_event

_WORK = frozenset({DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING})


def plan_duty(waypoints, initial_state, minutes_to_first_midnight):
    """Drive through waypoints in order, inserting rests whenever a rule allows no more driving.

    Times are integer minutes since trip start. minutes_to_first_midnight is the offset of the first
    home-terminal midnight, 1 to 1440; a trip starting at exactly 00:00 passes 1440. location and
    remark stay None for the planner to backfill. Nothing is emitted after the final waypoint's work.
    """
    if not 1 <= minutes_to_first_midnight <= MINUTES_PER_DAY:
        raise ValueError(f"minutes_to_first_midnight must be 1 to {MINUTES_PER_DAY}, got {minutes_to_first_midnight}")
    miles = [waypoint.at_mile for waypoint in waypoints]
    if miles and miles[0] < 0:
        raise ValueError(f"first waypoint mile must be non-negative, got {miles[0]}")
    if any(later < earlier for earlier, later in zip(miles, miles[1:])):
        raise ValueError(f"waypoint miles must be non-decreasing, got {miles}")

    events = []
    state = initial_state
    clock = 0
    next_midnight = minutes_to_first_midnight
    mile = 0.0

    def emit(status, duration, kind=None):
        nonlocal state, clock, next_midnight
        while duration > 0:
            # Every DRIVING and ON_DUTY_NOT_DRIVING event is cut at midnight, whatever produced it,
            # so day_on_duty stays exact. Off-duty and sleeper rests stay whole so a 10-hour or
            # 34-hour rest still qualifies; split_at_midnight cuts them for the sheets.
            span = min(duration, next_midnight - clock) if status in _WORK else duration
            event = DutyEvent(status, clock, span, mile, kind=kind)
            events.append(event)
            state = apply_event(state, event)
            clock = event.end_min
            duration -= span
            while clock >= next_midnight:
                state = advance_day(state)
                next_midnight += MINUTES_PER_DAY

    for waypoint in waypoints:
        remaining = ceil_to_grid((waypoint.at_mile - mile) / AVG_SPEED_MPH * MINUTES_PER_HOUR)
        while remaining > 0:
            allowances = [floor_to_grid(rule.driving_allowance(state)) for rule in RULES]
            allowance = min(allowances)
            if allowance <= 0:
                rest = RULES[allowances.index(allowance)].rest_requirement()
                emit(rest.status, rest.duration_min, rest.kind)
                continue
            chunk = min(allowance, remaining, next_midnight - clock)
            emit(DutyStatus.DRIVING, chunk)
            remaining -= chunk
            mile += chunk / MINUTES_PER_HOUR * AVG_SPEED_MPH
        mile = waypoint.at_mile
        emit(DutyStatus.ON_DUTY_NOT_DRIVING, waypoint.duration_min, waypoint.kind)

    return events
