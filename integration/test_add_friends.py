"""Testing adding new friends."""

import asyncio
import logging
import os

import pytest
from Cryptodome.PublicKey import ECC
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import PKI_CURVE_NAME, EcPemKeyPair, digest_key
from common.messages import CansMessage, CansMsgId


class AddFriendsOkException(Exception):
    """Dummy exception raised to gracefully exit the event loop."""

    ...


class MockClient(Client):
    """Mock client."""

    def __init__(self, my_keys: EcPemKeyPair) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        account = Account()
        self.session_manager = SessionManager(
            keys=my_keys,
            account=account,
        )

    async def run(self) -> None:
        """Run dummy client application in the background."""
        # Connect to the server
        await asyncio.gather(  # noqa: FKA01
            self.session_manager.connect(
                url=f"wss://{self.server_hostname}:{self.server_port}",
                certpath=self.certpath,
                friends=[],
            ),
        )

    async def add_friend_and_wait_for_login_notification(
        self, peer: str
    ) -> None:
        """Add friend and wait for PEER_LOGIN message."""
        self.log.debug(
            f"{self.session_manager.identity} sending ADD_FRIEND"
            + "message to the server..."
        )
        await self.session_manager.add_friend(peer)

        self.log.debug(
            f"{self.session_manager.identity} waiting for"
            + f" notification about {peer}"
        )

        while True:
            self.log.debug("Blocking on receive_system_message()...")
            message: CansMessage = (
                await self.session_manager.receive_system_message()
            )
            self.log.debug(
                f"Received message with id {message.header.msg_id}"
                + f" and payload: {message.payload}"
            )
            if (
                message.header.msg_id == CansMsgId.PEER_LOGIN
                and message.payload["peer"] == peer
            ):
                raise AddFriendsOkException()


def __generate_keys() -> EcPemKeyPair:
    """Generate key pair."""
    ec_key = ECC.generate(curve=PKI_CURVE_NAME)
    private_key = ec_key.export_key(format="PEM")
    public_key = ec_key.public_key().export_key(format="PEM")
    return private_key, public_key


async def impl_test_add_friends():
    """Async implementation of the test."""
    alice_secret, alice_public = __generate_keys()
    bob_secret, bob_public = __generate_keys()

    alice = MockClient(
        my_keys=(alice_secret, alice_public),
    )

    bob = MockClient(
        my_keys=(bob_secret, bob_public),
    )

    # Start Bob first...
    bob_future = asyncio.create_task(bob.run())
    # ...then wait a little...
    await asyncio.sleep(1)
    # ...and start Alice
    alice_future = asyncio.gather(
        alice.run(),
        alice.add_friend_and_wait_for_login_notification(
            digest_key(bob_public)
        ),
    )

    timeout = 5
    # Block on both futures
    await asyncio.wait_for(
        asyncio.gather(
            alice_future,
            bob_future,
        ),
        timeout,
    )


def test_add_friends():
    """Test adding new friends."""
    with pytest.raises(AddFriendsOkException):
        asyncio.get_event_loop().run_until_complete(impl_test_add_friends())
