"""DutyEvent, Waypoint and RestRequirement dataclasses."""
from dataclasses import dataclass

from .constants import GRID_RESOLUTION_MIN
from .enums import DutyStatus, StopKind


@dataclass(frozen=True, slots=True)
class DutyEvent:
    """One continuous block of a single duty status, in minutes since trip start."""

    status: DutyStatus
    start_min: int
    duration_min: int
    at_mile: float
    kind: StopKind | None = None
    location: str | None = None
    remark: str | None = None

    def __post_init__(self):
        if self.duration_min <= 0:
            raise ValueError(f"duration_min must be positive, got {self.duration_min}")
        if self.start_min < 0:
            raise ValueError(f"start_min must be non-negative, got {self.start_min}")
        if self.start_min % GRID_RESOLUTION_MIN or self.duration_min % GRID_RESOLUTION_MIN:
            raise ValueError(
                f"start_min and duration_min must be multiples of {GRID_RESOLUTION_MIN}, "
                f"got {self.start_min} and {self.duration_min}"
            )

    @property
    def end_min(self):
        return self.start_min + self.duration_min


@dataclass(frozen=True, slots=True)
class Waypoint:
    """A planned stop on the route. START uses duration_min 0."""

    at_mile: float
    kind: StopKind
    label: str
    duration_min: int


@dataclass(frozen=True, slots=True)
class RestRequirement:
    """What must happen when a rule binds. apply_event decides what the resulting event does to state."""

    status: DutyStatus
    duration_min: int
    kind: StopKind
