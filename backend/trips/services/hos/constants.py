"""Every HOS limit as a named integer in minutes, the single source of truth."""
import math

AVG_SPEED_MPH = 55  # planning assumption (spec §4), not regulatory
DRIVE_LIMIT_MIN = 660  # 11h driving, 49 CFR §395.3(a)(3)(i)
WINDOW_LIMIT_MIN = 840  # 14h window, 49 CFR §395.3(a)(2)
QUALIFYING_REST_MIN = 600  # 10h off duty resets driving, window and break, 49 CFR §395.3(a)(1)
BREAK_AFTER_DRIVE_MIN = 480  # 8h cumulative driving before a break, 49 CFR §395.3(a)(3)(ii)
BREAK_QUALIFY_MIN = 30  # 30 consecutive non-driving minutes clear the break, 49 CFR §395.3(a)(3)(ii)
CYCLE_LIMIT_MIN = 4200  # 70h on duty, 49 CFR §395.3(b)(2)
CYCLE_DAYS = 8  # rolling 8-day window, 49 CFR §395.3(b)(2)
RESTART_MIN = 2040  # 34h off duty restarts the cycle, 49 CFR §395.3(c)
FUEL_INTERVAL_MI = 1000  # fuel at least every 1,000 miles, assessment brief
FUEL_DURATION_MIN = 30  # fuel stop, on duty per 49 CFR §395.2
PICKUP_DURATION_MIN = 60  # assessment brief
DROPOFF_DURATION_MIN = 60  # assessment brief
BREAK_DURATION_MIN = 30  # length of the break the engine inserts, 49 CFR §395.3(a)(3)(ii)
GRID_RESOLUTION_MIN = 15  # smallest division of the RODS graph grid, 49 CFR §395.8
MINUTES_PER_DAY = 1440  # one 24-hour log period, 49 CFR §395.8
MINUTES_PER_HOUR = 60
RECAP_A_DAYS = 7  # recap box A, on duty in the last 7 days including today, as printed on the 70hr/8day form
RECAP_C_DAYS = 5  # recap box C, on duty in the last 5 days including today, as printed on the 70hr/8day form


def floor_to_grid(minutes):
    """Round down to a grid multiple. Used for allowances so a chunk never overruns a limit."""
    return math.floor(minutes / GRID_RESOLUTION_MIN) * GRID_RESOLUTION_MIN


def ceil_to_grid(minutes):
    """Round up to a grid multiple. Used for distance-derived durations so time is never understated."""
    return math.ceil(minutes / GRID_RESOLUTION_MIN) * GRID_RESOLUTION_MIN
