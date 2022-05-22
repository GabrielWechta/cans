"""Test notfiications on peer login and logout."""

import asyncio
import logging
import os
from typing import Callable

import pytest
import websockets.client as ws
from Cryptodome.PublicKey import ECC
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import PKI_CURVE_NAME, EcPemKeyPair, digest_key
from common.messages import CansMessage, CansMsgId


class NotificationsOkException(Exception):
    """Dummy exception raised to gracefully exit the event loop."""

    ...


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
        self,
        my_keys: EcPemKeyPair,
        peer_pub_key: str,
        session_manager_constructor: Callable,
    ) -> None:
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
        self.session_manager = session_manager_constructor(
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

    async def wait_for_notification(self) -> None:
        """Wait for login/logout notifications from the server."""
        login_notif_received = False
        while True:
            timeout = 5
            message: CansMessage = await asyncio.wait_for(
                self.session_manager.receive_system_message(), timeout
            )
            if message.header.msg_id == CansMsgId.PEER_LOGIN:
                login_notif_received = True
            elif message.header.msg_id == CansMsgId.PEER_LOGOUT:
                if login_notif_received:
                    raise NotificationsOkException()
                else:
                    self.log.error("Received PEER_LOGOUT but no PEER_LOGIN")


def __generate_keys() -> EcPemKeyPair:
    """Generate key pair."""
    ec_key = ECC.generate(curve=PKI_CURVE_NAME)
    private_key = ec_key.export_key(format="PEM")
    public_key = ec_key.public_key().export_key(format="PEM")
    return private_key, public_key


async def impl_test_notifications():
    """Async implementation of the test."""
    alice_secret, alice_public = __generate_keys()
    bob_secret, bob_public = __generate_keys()

    alice = MockClient(
        my_keys=(alice_secret, alice_public),
        peer_pub_key=digest_key(bob_public),
        session_manager_constructor=SessionManager,
    )

    # Start running the Alice client in the background
    asyncio.create_task(alice.run())

    # Give Alice some time to shake hands with the server
    await asyncio.sleep(1)

    # Start Alice's friend in the background
    bob = MockClient(
        my_keys=(bob_secret, bob_public),
        peer_pub_key=digest_key(alice_public),
        session_manager_constructor=MockSessionManager,
    )
    asyncio.create_task(bob.run())

    await alice.wait_for_notification()


def test_notifications():
    """Test login/logout notifications."""
    with pytest.raises(NotificationsOkException):
        asyncio.get_event_loop().run_until_complete(impl_test_notifications())