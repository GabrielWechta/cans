"""User message sent between two peers."""

from common.keys.PubKeyDigest import PubKeyDigest
from common.messages.CansMessage import CansMessage
from common.messages.CansMsgId import CansMsgId


class UserMessage(CansMessage):
    """User message."""

    def __init__(self, receiver: PubKeyDigest) -> None:
        """Create a CANS user message to a peer."""
        super().__init__()
        self.header.msg_id = CansMsgId.USER_MESSAGE
        self.header.receiver = receiver
