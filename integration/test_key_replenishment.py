"""Test replenishing one-time keys."""

import asyncio
import logging
import os
from typing import Set

import pytest
from cans_client import Client
from cans_client.session_manager_client import SessionManager
from cans_common.keys import EcPemKeyPair, digest_key, generate_keys
from cans_common.messages import CansMessage
from olm import Account


class KeyReplenishmentOkException(Exception):
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
        raise KeyReplenishmentOkException()


class MockClient(Client):
    """Mock client."""

    def __init__(self, my_keys: EcPemKeyPair, friends: Set[str]) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.friends = friends

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
            friends=self.friends,
        )


async def impl_test_key_replenishment():
    """Async implementation of the test."""
    alice_secret, alice_public = generate_keys()
    alice = MockClient(
        my_keys=(alice_secret, alice_public),
        friends=set(),
    )

    # Start running the Alice client in the background
    alice_future = asyncio.create_task(alice.run())

    for _ in range(8):
        # Run a couple of peers in the background to
        # deplete Alice's one-time keys
        peer = MockClient(
            my_keys=generate_keys(),
            friends={digest_key(alice_public)},
        )
        asyncio.create_task(peer.run())
    timeout = 5
    await asyncio.wait_for(alice_future, timeout)


def test_key_replenishment():
    """Test one-time keys replenishment."""
    with pytest.raises(KeyReplenishmentOkException):
        asyncio.get_event_loop().run_until_complete(
            impl_test_key_replenishment()
        )
