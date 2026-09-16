"""HOS rule classes and the active rule tuple, whose order is the tie-break order."""
from .constants import (
    AVG_SPEED_MPH,
    BREAK_AFTER_DRIVE_MIN,
    BREAK_DURATION_MIN,
    CYCLE_LIMIT_MIN,
    DRIVE_LIMIT_MIN,
    FUEL_DURATION_MIN,
    FUEL_INTERVAL_MI,
    MINUTES_PER_HOUR,
    QUALIFYING_REST_MIN,
    RESTART_MIN,
    WINDOW_LIMIT_MIN,
)
from .enums import DutyStatus, StopKind
from .events import RestRequirement


class SeventyHourCycleRule:
    """No driving after 70 on-duty hours in 8 days, 49 CFR §395.3(b). Cleared by a 34-hour restart, §395.3(c)."""

    def driving_allowance(self, state):
        return max(0, CYCLE_LIMIT_MIN - state.cycle_min)

    def rest_requirement(self):
        return RestRequirement(DutyStatus.OFF_DUTY, RESTART_MIN, StopKind.RESTART)


class FourteenHourWindowRule:
    """No driving after the 14th hour since work started, 49 CFR §395.3(a)(2)."""

    def driving_allowance(self, state):
        return max(0, WINDOW_LIMIT_MIN - state.window_min)

    def rest_requirement(self):
        return RestRequirement(DutyStatus.SLEEPER_BERTH, QUALIFYING_REST_MIN, StopKind.REST)


class ElevenHourRule:
    """No more than 11 hours driving after 10 consecutive hours off, 49 CFR §395.3(a)(3)(i)."""

    def driving_allowance(self, state):
        return max(0, DRIVE_LIMIT_MIN - state.driving_min)

    def rest_requirement(self):
        return RestRequirement(DutyStatus.SLEEPER_BERTH, QUALIFYING_REST_MIN, StopKind.REST)


class ThirtyMinuteBreakRule:
    """A 30-minute non-driving break after 8 cumulative driving hours, 49 CFR §395.3(a)(3)(ii)."""

    def driving_allowance(self, state):
        return max(0, BREAK_AFTER_DRIVE_MIN - state.since_break_min)

    def rest_requirement(self):
        return RestRequirement(DutyStatus.OFF_DUTY, BREAK_DURATION_MIN, StopKind.BREAK)


class FuelStopRule:
    """Fuel at least every 1,000 miles.

    Operational, from the assessment brief, not 49 CFR. It is shaped as a rule anyway so that
    miles_since_fuel can live in DriverState like every other accumulator, instead of being
    special-cased in the engine loop. Fueling is on-duty time under 49 CFR §395.2.
    """

    def driving_allowance(self, state):
        return max(0, int((FUEL_INTERVAL_MI - state.miles_since_fuel) / AVG_SPEED_MPH * MINUTES_PER_HOUR))

    def rest_requirement(self):
        return RestRequirement(DutyStatus.ON_DUTY_NOT_DRIVING, FUEL_DURATION_MIN, StopKind.FUEL)


# Tuple order is the tie-break when several rules allow zero driving, and the only place priority is encoded.
# Stronger rests come first because a weaker rest cannot clear a stronger limit: a 10-hour rest cannot restore
# an exhausted 70-hour cycle, so the cycle must win over the window and 11-hour rules; a 30-minute break cannot
# restore the 14-hour window or 11 driving hours, so those must win over the break.
RULES = (
    SeventyHourCycleRule(),
    FourteenHourWindowRule(),
    ElevenHourRule(),
    ThirtyMinuteBreakRule(),
    FuelStopRule(),
)


class AdverseDrivingRule:
    """Adverse driving conditions extension, 49 CFR §395.1(b)(1). Out of scope: the brief rules it out."""

    def driving_allowance(self, state):
        raise NotImplementedError("49 CFR §395.1(b)(1) adverse driving conditions is not implemented")

    def rest_requirement(self):
        raise NotImplementedError("49 CFR §395.1(b)(1) adverse driving conditions is not implemented")


class SplitSleeperBerthRule:
    """Split sleeper berth provision, 49 CFR §395.1(g). Out of scope."""

    def driving_allowance(self, state):
        raise NotImplementedError("49 CFR §395.1(g) split sleeper berth is not implemented")

    def rest_requirement(self):
        raise NotImplementedError("49 CFR §395.1(g) split sleeper berth is not implemented")


class ShortHaulRule:
    """Short-haul exception, 49 CFR §395.1(e). Out of scope."""

    def driving_allowance(self, state):
        raise NotImplementedError("49 CFR §395.1(e) short-haul exception is not implemented")

    def rest_requirement(self):
        raise NotImplementedError("49 CFR §395.1(e) short-haul exception is not implemented")


class SixtyHourCycleRule:
    """60 hours in 7 days cycle, 49 CFR §395.3(b). Out of scope: the brief fixes the 70-hour/8-day cycle."""

    def driving_allowance(self, state):
        raise NotImplementedError("49 CFR §395.3(b) 60-hour/7-day cycle is not implemented")

    def rest_requirement(self):
        raise NotImplementedError("49 CFR §395.3(b) 60-hour/7-day cycle is not implemented")
