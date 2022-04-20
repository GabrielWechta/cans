"""Sunny day test scenarios."""

import logging

import websockets.client as ws

from client import Client
from client.key_manager import KeyManager
from client.session_manager_client import SessionManager
from common.keys import PubKeyDigest


class MockSessionManager(SessionManager):
    """Mock session manager."""

    def __init__(
        self, key_manager: KeyManager, hardcoded_peer: PubKeyDigest
    ) -> None:
        """Construct the mock session manager."""
        super().__init__(key_manager, hardcoded_peer)
        self.log = logging.getLogger()

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Mock upstream handler."""
        pass

    async def _handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Mock downstream handler."""
        pass


def test_connection():
    """Test connecting to the server."""
    mock_peer = "BobPubKeyDigest"
    client = Client("AlicePubKeyDigest", mock_peer)
    client.session_manager = MockSessionManager(client.key_manager, mock_peer)
    client.run()
