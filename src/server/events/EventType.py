"""Session event type enumeration."""

from enum import IntEnum, unique


@unique
class EventType(IntEnum):
    """Session event type."""

    MESSAGE = 0
    LOGIN = 1
    LOGOUT = 2
