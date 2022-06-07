"""Test server connection and handshake."""

import asyncio
import logging
import os

import pytest
import websockets.client as ws
from olm import Account
from websockets.exceptions import ConnectionClosed

from client import Client
from client.session_manager_client import SessionManager
from common.connection import CansStatusCode
from common.keys import EcPemKeyPair, generate_keys


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

    def __init__(self, keys: EcPemKeyPair) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        account = Account()
        self.session_manager = MockSessionManager(
            keys=keys,
            account=account,
        )

    def run(self) -> None:
        """Run dummy client application. Do not try handling exceptions."""
        self.event_loop.run_until_complete(
            asyncio.gather(  # noqa: FKA01
                # Connect to the server...
                self.session_manager.connect(
                    url=f"wss://{self.server_hostname}:{self.server_port}",
                    certpath=self.certpath,
                    friends=set(),
                ),
                # ...and handle incoming messages
                self._handle_downstream_user_traffic(),
                self._handle_downstream_system_traffic(),
            )
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
    client = MockClient(generate_keys())
    client.run()


def test_failed_authentication():
    """Test failed authentication."""
    # Use non-corresponding keys
    private_key, _ = generate_keys()
    _, public_key = generate_keys()
    # Expect authentication failure and connection abort
    with pytest.raises(ConnectionClosed) as excinfo:
        client = MockClient((private_key, public_key))
        client.run()

    assert (
        excinfo.value.code == CansStatusCode.AUTH_FAILURE
    ), "Invalid status code"
