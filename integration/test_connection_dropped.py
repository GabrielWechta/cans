"""Test server connection and handshake."""

import asyncio
import logging
import os
from typing import Callable

import websockets.client as ws
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import KeyPair


class FaultyClientException(Exception):
    """Dummy exception raised to test abrupt disconnect."""

    ...


class FaultySessionManager(SessionManager):
    """Faulty session manager."""

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Mock upstream handler."""
        raise FaultyClientException()

    async def _handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Mock downstream handler."""
        raise FaultyClientException()


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

    def __init__(
        self, keys: KeyPair, session_manager_factory: Callable
    ) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        account = Account()
        self.session_manager = session_manager_factory(
            keys=keys, account=account
        )

    async def _handle_downstream_user_traffic(self) -> None:
        """Mock user downstream handler."""
        self.log.debug("Mock user downstream handler called at client level")

    async def _handle_downstream_system_traffic(self) -> None:
        """Mock control downstream handler."""
        self.log.debug(
            "Mock control downstream handler called at client level"
        )


def test_connection_dropped():
    """Test server's behaviour on connection dropped."""
    # Run a fault client that immediately drops the connection
    faulty_client = MockClient(
        ("test_connection_dropped_faulty", "test_connection_dropped_faulty"),
        FaultySessionManager,
    )
    try:
        faulty_client.run()
    except FaultyClientException:
        faulty_client.log.info("Faulty client terminated abruptly")

    good_client = MockClient(
        ("test_connection_dropped_good", "test_connection_dropped_good"),
        MockSessionManager,
    )
    good_client.run()
    good_client.log.info(
        "================== test_connection_dropped: DONE =================="
    )
