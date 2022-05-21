"""Test concurrent connection of multiple users."""

import asyncio
import logging
import os

import pytest
from Cryptodome.PublicKey import ECC
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import PKI_CURVE_NAME, EcPemKeyPair, digest_key


class MultipleClientsOkException(Exception):
    """Dummy exception raised to gracefully exit the event loop."""

    ...


class MockClient(Client):
    """Mock client."""

    def __init__(self, my_keys: EcPemKeyPair, peer_pub_key: str) -> None:
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
                friends=[self.test_peer],
            ),
            self._send_message_to_peer(),
            self._receive_message_from_peer(),
        )

    async def _send_message_to_peer(self) -> None:
        """Send a test message to a peer."""
        # Give the other party time for login
        await asyncio.sleep(1)
        message = self.session_manager.user_message_to(
            self.test_peer, f"Hello {self.test_peer}"
        )

        self.log.debug(f"Sending message to {self.test_peer}...")
        await self.session_manager.send_message(message)

    async def _receive_message_from_peer(self) -> None:
        """Receive a test message from a peer."""
        timeout = 5
        try:
            message = await asyncio.wait_for(
                self.session_manager.receive_user_message(), timeout
            )
            self.log.debug(
                f"Received message {message.payload}"
                + f" from {message.header.sender}"
            )
            raise MultipleClientsOkException()
        except asyncio.exceptions.TimeoutError as e:
            self.log.error(
                f"Timed out while waiting for a message from {self.test_peer}!"
            )
            raise e


def __generate_keys() -> EcPemKeyPair:
    """Generate key pair."""
    ec_key = ECC.generate(curve=PKI_CURVE_NAME)
    private_key = ec_key.export_key(format="PEM")
    public_key = ec_key.public_key().export_key(format="PEM")
    return private_key, public_key


def test_multiple_clients():
    """Test running multiple users."""
    alice_secret, alice_public = __generate_keys()
    bob_secret, bob_public = __generate_keys()

    alice = MockClient(
        my_keys=(alice_secret, alice_public),
        peer_pub_key=digest_key(bob_public),
    )

    bob = MockClient(
        my_keys=(bob_secret, bob_public),
        peer_pub_key=digest_key(alice_public),
    )

    with pytest.raises(MultipleClientsOkException):
        asyncio.get_event_loop().run_until_complete(
            asyncio.gather(alice.run(), bob.run())
        )
