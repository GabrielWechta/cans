"""Class representing a client session with the server."""

import asyncio
from typing import List

import websockets.server as ws

from common.keys import PubKeyDigest


class ClientSession:
    """Class representing a client session with the server."""

    def __init__(
        self, conn: ws.WebSocketServerProtocol, public_key_digest: PubKeyDigest
    ) -> None:
        """Initialize a client session."""
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.connection = conn
        self.public_key_digest = public_key_digest
        self.subscriptions: List[PubKeyDigest] = []
