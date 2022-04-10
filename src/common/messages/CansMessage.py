"""Define an abstract prototype for a CANS message."""

from common.keys.PubKeyDigest import PubKeyDigest


class CansMessage:
    """An abstract prototype for a CANS message."""

    def __init__(self) -> None:
        """Create a CANS message."""
        self.header = self.CansHeader()
        self.payload = None

    class CansHeader:
        """CANS header."""

        def __init__(self) -> None:
            """Create a CANS header."""
            self.sender: PubKeyDigest = None
            self.receiver: PubKeyDigest = None
            self.msg_id = None
