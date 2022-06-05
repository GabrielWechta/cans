"""Test notfiications on peer login and logout."""

import asyncio
import logging
import os
from typing import Callable, List, Set

import pytest
import websockets.client as ws
from Cryptodome.PublicKey import ECC
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import PKI_CURVE_NAME, EcPemKeyPair, digest_key
from common.messages import CansMessage, CansMsgId, cans_recv


class NotificationsOkException(Exception):
    """Dummy exception raised to gracefully exit the event loop."""

    ...


class DummySessionManager(SessionManager):
    """Dummy session manager that ignores all messages."""

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Mock an upstream handler."""
        self.log.debug(
            "Dummy upstream handler called at session manager level"
        )

    async def _handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Mock a downstream handler."""
        self.log.debug(
            "Dummy downstream handler called at session manager level"
        )


class OneTimeSessionManager(SessionManager):
    """Session manager that handles a single message in each direction."""

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle a single upstream message."""
        message = await self.upstream_message_queue.get()
        await self._handle_outgoing_message(conn, message)

    async def _handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Handle a single downstream message."""
        message = await cans_recv(conn)
        await self._handle_incoming_message(conn, message)


class MockClient(Client):
    """Mock client."""

    def __init__(
        self,
        my_keys: EcPemKeyPair,
        friends: Set[str],
        session_manager_constructor: Callable,
    ) -> None:
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
            friends=self.friends,
        )

    async def wait_for_notifications(
        self, expected_notifications: List[CansMsgId]
    ) -> None:
        """Wait for login/logout notifications from the server."""
        while True:
            if len(expected_notifications) == 0:
                # No more notifications to wait for
                raise NotificationsOkException()

            timeout = 5
            message: CansMessage = await asyncio.wait_for(
                self.session_manager.receive_system_message(), timeout
            )

            expected_msg_id = expected_notifications.pop(0)
            if message.header.msg_id != expected_msg_id:
                raise AssertionError(
                    f"Received notification {message.header.msg_id}"
                    + f" while expecting {expected_msg_id}"
                )

    async def initiate_conversation(self, friend: str) -> None:
        """Initiate a conversation with a friend and then disconnect."""
        # Send a message to the friend
        message, _ = self.session_manager.user_message_to(
            friend, "Hi Alice, this is Bob!"
        )
        await self.session_manager.send_message(message)


def __generate_keys() -> EcPemKeyPair:
    """Generate key pair."""
    ec_key = ECC.generate(curve=PKI_CURVE_NAME)
    private_key = ec_key.export_key(format="PEM")
    public_key = ec_key.public_key().export_key(format="PEM")
    return private_key, public_key


async def impl_test_notifications_for_a_friend():
    """Async implementation of the test."""
    alice_secret, alice_public = __generate_keys()
    bob_secret, bob_public = __generate_keys()

    alice = MockClient(
        my_keys=(alice_secret, alice_public),
        friends={digest_key(bob_public)},
        session_manager_constructor=SessionManager,
    )

    # Start running the Alice client in the background
    asyncio.create_task(alice.run())

    # Give Alice some time to shake hands with the server
    await asyncio.sleep(1)

    # Start Alice's friend in the background
    bob = MockClient(
        my_keys=(bob_secret, bob_public),
        friends={digest_key(alice_public)},
        session_manager_constructor=DummySessionManager,
    )
    asyncio.create_task(bob.run())

    await alice.wait_for_notifications(
        [CansMsgId.PEER_LOGIN, CansMsgId.PEER_LOGOUT]
    )


async def impl_test_notifications_for_a_stranger():
    """Async implementation of the test."""
    alice_secret, alice_public = __generate_keys()
    bob_secret, bob_public = __generate_keys()

    # Alice has no friends
    alice = MockClient(
        my_keys=(alice_secret, alice_public),
        friends=set(),
        session_manager_constructor=SessionManager,
    )

    # Start running the Alice client in the background
    asyncio.create_task(alice.run())

    # Give Alice some time to shake hands with the server
    await asyncio.sleep(1)

    # Let Bob initiate a conversation with Alice
    bob = MockClient(
        my_keys=(bob_secret, bob_public),
        friends={digest_key(alice_public)},
        # Bob's session will time out after some time
        session_manager_constructor=OneTimeSessionManager,
    )

    await asyncio.gather(  # noqa: FKA01
        bob.run(),
        alice.wait_for_notifications([CansMsgId.PEER_LOGOUT]),
        bob.initiate_conversation(digest_key(alice_public)),
    )


def test_notifications_for_a_friend():
    """Test login/logout notifications for a friend."""
    with pytest.raises(NotificationsOkException):
        asyncio.get_event_loop().run_until_complete(
            impl_test_notifications_for_a_friend()
        )


def test_notifications_for_a_stranger():
    """Test logout notifications for a stranger that initiated conversation."""
    with pytest.raises(NotificationsOkException):
        asyncio.get_event_loop().run_until_complete(
            impl_test_notifications_for_a_stranger()
        )
