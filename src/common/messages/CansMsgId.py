"""Define CANS message IDs."""

from enum import IntEnum, unique


@unique
class CansMsgId(IntEnum):
    """CANS message ID."""

    USER_MESSAGE = 0
    SHARE_CONTACTS = 1
    SERVER_HELLO = 2
    PEER_UNAVAILABLE = 3
