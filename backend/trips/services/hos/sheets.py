"""DaySheet assembly, padding and totals for each calendar day."""
from dataclasses import dataclass

from .constants import (
    CYCLE_LIMIT_MIN,
    MINUTES_PER_DAY,
    RECAP_A_DAYS,
    RECAP_C_DAYS,
)
from .enums import DutyStatus


@dataclass(frozen=True, slots=True)
class Recap:
    """The paper form's end-of-day recap for 70hr/8day drivers, in minutes."""

    on_duty_today: int  # one box on the form: the total of lines 3 and 4
    a_on_duty_last_7_days: int
    b_available_tomorrow: int  # CYCLE_LIMIT_MIN minus A, never negative
    c_on_duty_last_5_days: int


@dataclass(frozen=True, slots=True)
class DaySheet:
    """One RODS page. Minutes are from that day's home-terminal midnight, 0 to 1440."""

    date_index: int
    segments: tuple[tuple[DutyStatus, int, int], ...]  # (status, start, end), adjacent same-status runs merged
    totals: dict[DutyStatus, int]
    total_miles_driving: float
    remarks: tuple[tuple[int, str | None], ...]  # (at_min, location)
    recap: Recap


def _add_remark(remarks, at_min, location):
    """A driver writes a city once per place, so a status change at the same place adds nothing."""
    if not remarks or remarks[-1][1] != location:
        remarks.append((at_min, location))


def _day_log(events, day_start, is_first_day, is_last_day):
    """Segments and remarks for one day.

    Remarks go at status changes whose location differs from the previous remark. A change takes the
    location of the event beginning the new status; the change into trailing padding takes the location
    where the driver was released. A day opens with a remark at minute 0 carrying the location in progress
    at midnight: always after the first day, and on the first day when the trip itself starts at midnight.
    """
    segments = []
    remarks = []

    first_start = events[0].start_min - day_start
    if not is_first_day or first_start == 0:
        remarks.append((0, events[0].location))

    if is_first_day and first_start > 0:
        segments.append([DutyStatus.OFF_DUTY, 0, first_start])

    for event in events:
        start, end = event.start_min - day_start, event.end_min - day_start
        if segments and segments[-1][0] is event.status:
            segments[-1][2] = end
            continue
        if segments:
            _add_remark(remarks, start, event.location)
        segments.append([event.status, start, end])

    last_end = segments[-1][2]
    if is_last_day and last_end < MINUTES_PER_DAY:
        if segments[-1][0] is DutyStatus.OFF_DUTY:
            segments[-1][2] = MINUTES_PER_DAY
        else:
            _add_remark(remarks, last_end, events[-1].location)
            segments.append([DutyStatus.OFF_DUTY, last_end, MINUTES_PER_DAY])

    return tuple(tuple(segment) for segment in segments), tuple(remarks)


def _miles_driven_per_day(day_buckets):
    """Road miles driven on each day: every driving event spans from its own mile to the next event's mile.

    Miles come from the events' positions, not from driving minutes at AVG_SPEED_MPH. Driving time to a stop is
    rounded up to the 15-minute grid, so minutes times speed overstates the distance; positions do not, because
    the engine sets the mile to the stop's true mile on arrival. So a trip's sheets add up to its route distance.

    Consecutive driving events that start at the same mile are one drive cut at midnight by split_at_midnight;
    their span is shared between the days in proportion to the minutes driven on each.
    """
    flat = [(day, event) for day, events in enumerate(day_buckets) for event in events]
    miles = [0.0] * len(day_buckets)
    index = 0
    while index < len(flat):
        day, event = flat[index]
        if event.status is not DutyStatus.DRIVING:
            index += 1
            continue
        run_end = index + 1
        while run_end < len(flat) and flat[run_end][1].status is DutyStatus.DRIVING and flat[run_end][1].at_mile == event.at_mile:
            run_end += 1
        end_mile = flat[run_end][1].at_mile if run_end < len(flat) else event.at_mile
        run = flat[index:run_end]
        run_minutes = sum(piece.duration_min for _, piece in run)
        for piece_day, piece in run:
            miles[piece_day] += (end_mile - event.at_mile) * piece.duration_min / run_minutes
        index = run_end
    return miles


def _window_total(on_duty, prior_cycle_min, restart_day_indices, day, days):
    """On-duty minutes over the `days` days ending today, reaching back no further than the latest restart.

    The restart day itself is included: a 34-hour rest outlasts a calendar day, so any on-duty time on
    the day a restart completes comes after it. Prior cycle hours count only while the window still
    reaches before the trip and no restart has happened; they are one lump, so this errs high, never low.
    """
    first = day - days + 1
    restarts = [index for index in restart_day_indices if index <= day]
    if restarts:
        first = max(first, max(restarts))
    total = sum(on_duty[max(0, first):day + 1])
    return total + prior_cycle_min if first < 0 else total


def build_sheets(day_buckets, minutes_to_first_midnight, prior_cycle_min, restart_day_indices):
    """Turn split_at_midnight output into one full 24-hour DaySheet per calendar day.

    Leading time on the first day and trailing time on the last day are padded as OFF_DUTY.
    restart_day_indices are the days on which a 34-hour restart completes; the planner derives them
    from event kinds. The recap is computed from these sheets' own totals, never from DriverState.day_on_duty.

    The recap deliberately uses a 7-day window for A while DriverState.cycle_min sums 8 days. cycle_min is
    the live 70-hour cycle the rule enforces right now. Box A feeds box B, "hours available tomorrow":
    tomorrow's 8-day window is tomorrow plus the last 7 days, so CYCLE_LIMIT_MIN minus a 7-day A is what
    tomorrow allows. Same limit, different question, so the two numbers differ by design.
    """
    first_day_start = minutes_to_first_midnight - MINUTES_PER_DAY
    last_index = len(day_buckets) - 1

    logs = []
    on_duty = []
    for index, events in enumerate(day_buckets):
        segments, remarks = _day_log(
            events, first_day_start + index * MINUTES_PER_DAY, index == 0, index == last_index
        )
        totals = dict.fromkeys(DutyStatus, 0)
        for status, start, end in segments:
            totals[status] += end - start
        if sum(totals.values()) != MINUTES_PER_DAY:
            raise ValueError(f"day {index} covers {sum(totals.values())} minutes, expected {MINUTES_PER_DAY}")
        logs.append((segments, remarks, totals))
        on_duty.append(totals[DutyStatus.DRIVING] + totals[DutyStatus.ON_DUTY_NOT_DRIVING])

    miles_driven = _miles_driven_per_day(day_buckets)
    sheets = []
    for index, (segments, remarks, totals) in enumerate(logs):
        a_total = _window_total(on_duty, prior_cycle_min, restart_day_indices, index, RECAP_A_DAYS)
        sheets.append(DaySheet(
            date_index=index,
            segments=segments,
            totals=totals,
            total_miles_driving=miles_driven[index],
            remarks=remarks,
            recap=Recap(
                on_duty_today=on_duty[index],
                a_on_duty_last_7_days=a_total,
                b_available_tomorrow=max(0, CYCLE_LIMIT_MIN - a_total),
                c_on_duty_last_5_days=_window_total(on_duty, prior_cycle_min, restart_day_indices, index, RECAP_C_DAYS),
            ),
        ))
    return sheets
