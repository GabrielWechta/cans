"""Test server connection and handshake."""

import asyncio
import logging
import os

import pytest
import websockets.client as ws
from Cryptodome.PublicKey import ECC
from olm import Account
from websockets.exceptions import ConnectionClosed

from client import Client
from client.session_manager_client import SessionManager
from common.keys import PKI_CURVE_NAME, EcPemKeyPair


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

        # TODO: Remove once beta is released and presented
        self.echo_peer_id = (
            "e12dc2da85f995a528d34b4acdc539a720b2bc4912bc1c32c322b201134d3ed6"
        )

        account = Account()
        self.session_manager = MockSessionManager(
            keys=keys,
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


def __generate_keys() -> EcPemKeyPair:
    """Generate key pair."""
    ec_key = ECC.generate(curve=PKI_CURVE_NAME)
    private_key = ec_key.export_key(format="PEM")
    public_key = ec_key.public_key().export_key(format="PEM")
    return private_key, public_key


def test_basic_connect():
    """Test connecting to the server."""
    client = MockClient(__generate_keys())
    client.run()


def test_failed_authentication():
    """Test failed authentication."""
    # Use non-corresponding keys
    private_key, _ = __generate_keys()
    _, public_key = __generate_keys()
    # Expect authentication failure and connection abort
    with pytest.raises(ConnectionClosed):
        client = MockClient((private_key, public_key))
        client.run()
