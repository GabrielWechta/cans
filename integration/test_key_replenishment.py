"""Test concurrent connection of multiple users."""

import asyncio
import logging
import os

import pytest
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import KeyPair, PubKey
from common.messages import CansMessage


class KeyReplenishmentSuccess(Exception):
    """Dummy exception raised to gracefully exit the event loop."""

    ...


class MockSessionManager(SessionManager):
    """Mock session manager."""

    async def _handle_message_replenish_one_time_keys_req(
        self, message: CansMessage
    ) -> None:
        """Mock handler of one-time keys replenishment request."""
        count = message.payload["count"]
        self.log.debug(
            f"Successfully received a request to replenish {count} keys"
        )
        raise KeyReplenishmentSuccess()


class MockClient(Client):
    """Mock client."""

    def __init__(self, my_keys: KeyPair, peer_pub_key: PubKey) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.test_peer = peer_pub_key

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        account = Account()
        self.session_manager = MockSessionManager(
            keys=my_keys,
            account=account,
        )

    async def run(self) -> None:
        """Run dummy client application."""
        # Connect to the server
        await self.session_manager.connect(
            url=f"wss://{self.server_hostname}:{self.server_port}",
            certpath=self.certpath,
            friends=[self.test_peer],
        )


async def impl_test_key_replenishment():
    """Async implementation of the test."""
    alice = MockClient(
        my_keys=("Alice", "Alice"),
        peer_pub_key="Bob",  # Non-existent peer
    )

    # Start running the Alice client in the background
    alice_future = alice.run()

    for i in range(8):
        # Run a couple of peers in the background to
        # deplete Alice's one-time keys
        peer = MockClient(
            my_keys=(f"Peer_{i}", f"Peer_{i}"),
            peer_pub_key="Alice",
        )
        asyncio.create_task(peer.run())
    timeout = 5
    await asyncio.wait_for(alice_future, timeout)


def test_key_replenishment():
    """Test one-time keys replenishment."""
    with pytest.raises(KeyReplenishmentSuccess):
        asyncio.get_event_loop().run_until_complete(
            impl_test_key_replenishment()
        )
