"""Midnight splitting of duty events into per-day buckets."""
from dataclasses import replace

from .constants import MINUTES_PER_DAY


def split_at_midnight(events, minutes_to_first_midnight):
    """Bucket events by home-terminal calendar day in one pass, cutting any event that straddles midnight.

    Bucket 0 is the day the trip starts. start_min stays absolute minutes since trip start. The second
    half of a cut event keeps every other field (status, kind, location, mile, remark). A rest covering
    whole days yields one full-day piece per day, so day indices stay contiguous.
    """
    if not 1 <= minutes_to_first_midnight <= MINUTES_PER_DAY:
        raise ValueError(f"minutes_to_first_midnight must be 1 to {MINUTES_PER_DAY}, got {minutes_to_first_midnight}")

    days = [[]]
    boundary = minutes_to_first_midnight
    for event in events:
        start = event.start_min
        while start >= boundary:
            days.append([])
            boundary += MINUTES_PER_DAY
        while event.end_min > boundary:
            days[-1].append(replace(event, start_min=start, duration_min=boundary - start))
            start = boundary
            days.append([])
            boundary += MINUTES_PER_DAY
        days[-1].append(event if start == event.start_min else replace(event, start_min=start, duration_min=event.end_min - start))

    return days if events else []
