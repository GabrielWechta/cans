"""Type representing a session event."""

from enum import IntEnum, unique
from typing import Any, Dict, Union

from common.messages import CansMessage


@unique
class EventType(IntEnum):
    """Session event type."""

    MESSAGE = 0
    LOGIN = 1
    LOGOUT = 2


class SessionEvent:
    """A session event."""

    def __init__(
        self,
        event_type: EventType = EventType.MESSAGE,
        payload: Union[CansMessage, Dict[str, Any]] = None,
    ) -> None:
        """Instantiate a new event."""
        self.event_type = event_type
        self.payload = payload
