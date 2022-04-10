"""Peer unavailable notification."""

from common.keys.PubKeyDigest import PubKeyDigest
from common.messages.CansMessage import CansMessage
from common.messages.CansMsgId import CansMsgId


class PeerUnavailable(CansMessage):
    """Peer unavailable notification."""

    def __init__(self, receiver: PubKeyDigest, peer: PubKeyDigest) -> None:
        """Create a peer unavailable notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_UNAVAILABLE
        self.header.receiver = receiver
        self.header.sender = ""
        self.payload = {"peer": peer}
