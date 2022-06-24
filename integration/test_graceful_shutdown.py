"""Test graceful shutdown of the client application."""

import asyncio
import logging
import os

from cans_client import Client
from cans_client.session_manager_client import SessionManager
from cans_common.keys import EcPemKeyPair, generate_keys
from olm import Account


class MockClient(Client):
    """Mock client."""

    def __init__(self, keys: EcPemKeyPair):
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.echo_peer_id = (
            "e12dc2da85f995a528d34b4acdc539a720b2bc4912bc1c32c322b201134d3ed6"
        )

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        self.shutdown_graceful = False

        account = Account()
        self.session_manager = SessionManager(
            keys=keys,
            account=account,
        )

    async def _handle_downstream_user_traffic(self) -> None:
        """Handle downstream user messages."""
        while True:
            await asyncio.sleep(1)
            raise Exception()

    async def _handle_downstream_system_traffic(self) -> None:
        """Handle downstream server messages."""
        while True:
            message = await self.session_manager.receive_system_message()
            assert message

    async def _do_graceful_shutdown(self) -> None:
        """Shut down the application gracefully."""
        await self.session_manager.shutdown()
        self.shutdown_graceful = True


def test_graceful_shutdown():
    """Test graceful shutdown."""
    client = MockClient(generate_keys())
    client.run()
    assert client.shutdown_graceful
