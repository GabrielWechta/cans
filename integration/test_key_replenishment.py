"""Test replenishing one-time keys."""

import asyncio
import logging
import os
from typing import List, Tuple

import pytest
from Cryptodome.PublicKey import ECC
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import PKI_CURVE_NAME, KeyPair, digest_key
from common.messages import CansMessage


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

    def __init__(self, my_keys: KeyPair, friends: List[str]) -> None:
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


def __generate_keys() -> Tuple[str, str]:
    """Generate key pair."""
    ec_key = ECC.generate(curve=PKI_CURVE_NAME)
    private_key = ec_key.export_key(format="PEM")
    public_key = ec_key.public_key().export_key(format="PEM")
    return private_key, public_key


async def impl_test_key_replenishment():
    """Async implementation of the test."""
    alice_secret, alice_public = __generate_keys()
    alice = MockClient(
        my_keys=(alice_secret, alice_public),
        friends=[],
    )

    # Start running the Alice client in the background
    alice_future = asyncio.create_task(alice.run())

    for _ in range(8):
        # Run a couple of peers in the background to
        # deplete Alice's one-time keys
        peer = MockClient(
            my_keys=__generate_keys(),
            friends=[digest_key(alice_public)],
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
