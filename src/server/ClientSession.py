"""Class representing a client session with the server."""

import asyncio
from typing import List

import websockets.server as ws


class ClientSession:
    """Class representing a client session with the server."""

    def __init__(
        self, conn: ws.WebSocketServerProtocol, public_key: str
    ) -> None:  # TODO: Public key type!
        """Initialize a client session."""
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.connection = conn
        self.public_key = public_key
        self.subscriptions: List[str] = []  # TODO: Public key type!
