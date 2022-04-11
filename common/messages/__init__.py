"""CANS application message API."""

from .message_api import cans_recv, cans_send
from .messages import (
    CansMessage,
    CansMsgId,
    PeerUnavailable,
    ServerHello,
    UserMessage,
)

# Touch the imports to silence flake8
assert cans_recv
assert cans_send
assert CansMessage
assert CansMsgId
assert PeerUnavailable
assert ServerHello
assert UserMessage
