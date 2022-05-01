"""Class representing a client session with the server."""

import asyncio
from typing import Dict, List

import websockets.server as ws

from common.keys import PubKeyDigest


class ClientSession:
    """Class representing a client session with the server."""

    def __init__(
        self,
        conn: ws.WebSocketServerProtocol,
        public_key_digest: PubKeyDigest,
        subscriptions: List[PubKeyDigest],
        identity_key: str,
        one_time_keys: Dict[str, str],
    ) -> None:
        """Initialize a client session."""
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.connection = conn
        self.public_key_digest = public_key_digest
        self.subscriptions = subscriptions
        self.identity_key = identity_key
        self.one_time_keys = one_time_keys
        self.hostname = conn.remote_address[0]
        self.port = conn.remote_address[1]

    def pop_one_time_key(self) -> str:
        """Pop double-ratchet one-time key."""
        return self.one_time_keys.pop(list(self.one_time_keys.keys())[0])

    def remaining_keys(self) -> int:
        """Get the count of remaining one-time keys."""
        return len(self.one_time_keys)

    def add_one_time_keys(self, keys: Dict[str, str]) -> None:
        """Append one-time keys."""
        self.one_time_keys.update(keys)
