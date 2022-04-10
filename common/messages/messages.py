"""Define CANS message formats."""

from enum import IntEnum, unique
from typing import Any

from common.keys import PubKeyDigest

CansSerial = str


@unique
class CansMsgId(IntEnum):
    """CANS message ID."""

    USER_MESSAGE = 0
    SHARE_CONTACTS = 1
    SERVER_HELLO = 2
    PEER_UNAVAILABLE = 3


class CansMessage:
    """An abstract prototype for a CANS message."""

    def __init__(self) -> None:
        """Create a CANS message."""
        self.header = self.CansHeader()
        self.payload: Any = None

    class CansHeader:
        """CANS header."""

        def __init__(self) -> None:
            """Create a CANS header."""
            self.sender: PubKeyDigest = None
            self.receiver: PubKeyDigest = None
            self.msg_id: CansMsgId = CansMsgId.USER_MESSAGE


class UserMessage(CansMessage):
    """User message."""

    def __init__(self, receiver: PubKeyDigest) -> None:
        """Create a CANS user message to a peer."""
        super().__init__()
        self.header.msg_id = CansMsgId.USER_MESSAGE
        self.header.receiver = receiver


class PeerUnavailable(CansMessage):
    """Peer unavailable notification."""

    def __init__(self, receiver: PubKeyDigest, peer: PubKeyDigest) -> None:
        """Create a peer unavailable notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_UNAVAILABLE
        self.header.receiver = receiver
        self.header.sender = ""
        self.payload = {"peer": peer}


class ServerHello(CansMessage):
    """Dummy handshake message.

    To be replaced with actual authentication.
    """

    def __init__(self) -> None:
        """Create a dummy handshake message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SERVER_HELLO
        self.header.receiver = ""
        self.payload = {"public_key": None}
