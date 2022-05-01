"""Test server connection and handshake."""

import asyncio
import logging
import os

import websockets.client as ws
from olm import Account

from client import Client
from client.session_manager_client import SessionManager


class MockSessionManager(SessionManager):
    """Mock session manager."""

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Mock upstream handler."""
        self.log.debug("Mock upstream handler called at session manager level")

    async def _handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Mock downstream handler."""
        self.log.debug(
            "Mock downstream handler called at session manager level"
        )


class MockClient(Client):
    """Mock client."""

    def __init__(self) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        pub_key, priv_key = ("test_basic_connect", "test_basic_connect")

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        account = Account()
        self.session_manager = MockSessionManager(
            keys=(pub_key, priv_key),
            account=account,
        )

    async def _handle_downstream_user_traffic(self) -> None:
        """Mock user downstream handler."""
        self.log.debug("Mock user downstream handler called at client level")

    async def _handle_downstream_system_traffic(self) -> None:
        """Mock control downstream handler."""
        self.log.debug(
            "Mock control downstream handler called at client level"
        )


def test_basic_connect():
    """Test connecting to the server."""
    client = MockClient()
    client.run()
    client.log.info(
        "================== test_basic_connect: DONE =================="
    )
