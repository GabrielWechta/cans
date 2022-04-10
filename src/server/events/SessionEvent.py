"""Type representing a session event."""

from typing import Any

from events.EventType import EventType


class SessionEvent:
    """A session event."""

    def __init__(
        self, event_type: EventType = EventType.MESSAGE, payload: Any = None
    ) -> None:
        """Instantiate a new event."""
        self.event_type = event_type
        self.payload = payload
