"""Type representing a session event."""

from enum import IntEnum, unique
from typing import Any, Dict, Union

from common.keys import PubKeyDigest
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
        event_type: EventType,
        payload: Union[CansMessage, Dict[str, Any]] = None,
    ) -> None:
        """Instantiate a new event."""
        self.event_type = event_type
        self.payload = payload


class MessageEvent(SessionEvent):
    """An incoming message event."""

    def __init__(self, message: CansMessage) -> None:
        """Initialize an incoming message event."""
        super().__init__(EventType.MESSAGE, message)


class LoginEvent(SessionEvent):
    """A user login event."""

    def __init__(self, peer_key_digest: PubKeyDigest) -> None:
        """Initialize a login event."""
        super().__init__(EventType.LOGIN, {"peer": peer_key_digest})


class LogoutEvent(SessionEvent):
    """A user logout event."""

    def __init__(self, peer_key_digest: PubKeyDigest) -> None:
        """Initialize a logout event."""
        super().__init__(EventType.LOGOUT, {"peer": peer_key_digest})
