"""DutyStatus and StopKind enums."""
from enum import Enum, StrEnum


class DutyStatus(Enum):
    """Duty statuses in paper-form row order, top to bottom."""

    OFF_DUTY = 0
    SLEEPER_BERTH = 1
    DRIVING = 2
    ON_DUTY_NOT_DRIVING = 3

    @property
    def row_index(self):
        return self.value

    @property
    def is_driving(self):
        return self is DutyStatus.DRIVING


class StopKind(StrEnum):
    """Stop categories. Values are the strings the API emits; one enum drives map markers and timeline rows."""

    START = "START"
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    FUEL = "FUEL"
    BREAK = "BREAK"
    REST = "REST"
    RESTART = "RESTART"
