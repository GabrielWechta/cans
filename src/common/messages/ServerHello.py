"""Dummy message for PoC purposes.

To be replaced with actual authentication.
"""

from common.messages.CansMessage import CansMessage
from common.messages.CansMsgId import CansMsgId


class ServerHello(CansMessage):
    """Dummy handshake message."""

    def __init__(self) -> None:
        """Create a dummy handshake message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SERVER_HELLO
        self.header.receiver = ""
        self.payload = {"public_key": None}
