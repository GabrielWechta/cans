"""Test graceful handling of OLM session errors."""


import asyncio
import logging
import os
from typing import Optional, Set

import pytest
from olm import Account

from client import Client
from client.session_manager_client import SessionManager
from common.keys import EcPemKeyPair, digest_key, generate_keys
from common.messages import CansMessage, CansMsgId


class SessionErrorOkException(Exception):
    """Dummy exception raised to gracefully exit the event loop."""

    ...


class MockSessionManager(SessionManager):
    """Cryptographically illiterate session manager."""

    def __init__(
        self,
        keys: EcPemKeyPair,
        account: Account,
        crypto_session_peer_override: Optional[str] = None,
    ) -> None:
        """Construct a mockable session manager."""
        super().__init__(keys, account)
        self.crypto_session_peer_override = crypto_session_peer_override

    def _encrypt_message_payload(self, message: CansMessage) -> CansMessage:
        """Encrypt different parts of the payload depending on message ID."""
        receiver = message.header.receiver
        msg_id = message.header.msg_id
        if msg_id == CansMsgId.USER_MESSAGE:
            # Use a faulty implementation when encrypting user messages
            message.payload["text"] = self._encrypt_text_faulty(
                receiver, message.payload["text"]
            )
            return message
        else:
            # For other traffic use parent implementation
            return super()._encrypt_message_payload(message)

    def _encrypt_text_faulty(self, receiver: str, payload: str) -> str:
        """Do faulty encryption of user message payload."""
        if self.crypto_session_peer_override:
            # Always use the same OLM session for encryption, regardless of
            # the actual receiver
            encrypt = self.session_sm.get_encryption_callback(
                self.crypto_session_peer_override
            )
        else:
            encrypt = self.session_sm.get_encryption_callback(receiver)
        olm_message = encrypt(payload)
        return olm_message.ciphertext

    async def _handle_message_get_one_time_key_resp(
        self, message: CansMessage
    ) -> None:
        """Handle message type GET_ONE_TIME_KEY_RESP."""
        await super()._handle_message_get_one_time_key_resp(message)
        # Successfully reset the session after session error
        raise SessionErrorOkException()


class MockClient(Client):
    """Mock client."""

    def __init__(
        self,
        keys: EcPemKeyPair,
        friends: Set,
        crypto_session_peer_override: Optional[str] = None,
    ) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        self.friends = friends

        account = Account()
        self.session_manager = MockSessionManager(
            keys=keys,
            account=account,
            crypto_session_peer_override=crypto_session_peer_override,
        )

    async def run(self) -> None:
        """Run dummy client application."""
        # Connect to the server
        await self.session_manager.connect(
            url=f"wss://{self.server_hostname}:{self.server_port}",
            certpath=self.certpath,
            friends=self.friends,
        )

    async def ping_peers(self) -> None:
        """Continually ping your peers."""
        while True:
            await asyncio.sleep(1)
            for peer in self.friends:
                message, _ = self.session_manager.user_message_to(
                    peer, f"Hello {peer}"
                )
                await self.session_manager.send_message(message)


async def impl_test_bad_message_format():
    """Async implementation of the test."""
    alice_secret, alice_public = generate_keys()
    bob_secret, bob_public = generate_keys()
    mallory_secret, mallory_public = generate_keys()

    # Instantiate three parties and let them all be friends with each other
    alice = MockClient(
        keys=(alice_secret, alice_public),
        friends={digest_key(bob_public), digest_key(mallory_public)},
        crypto_session_peer_override=None,
    )
    bob = MockClient(
        keys=(bob_secret, bob_public),
        friends={digest_key(alice_public), digest_key(mallory_public)},
        crypto_session_peer_override=None,
    )
    mallory = MockClient(
        keys=(mallory_secret, mallory_public),
        friends={digest_key(alice_public), digest_key(bob_public)},
        # Let Mallory be the broken client that always uses his session
        # context with Bob, even when encrypting messages to Alice
        crypto_session_peer_override=digest_key(bob_public),
    )

    # Let all parties connect to the server
    alice_task = asyncio.create_task(alice.run())
    bob_task = asyncio.create_task(bob.run())
    charlie_task = asyncio.create_task(mallory.run())
    # Give them some time
    await asyncio.sleep(3)

    timeout = 5
    await asyncio.wait_for(
        # Gather all tasks to catch any exceptions
        asyncio.gather(  # noqa: FKA01
            alice_task,
            bob_task,
            charlie_task,
            # Let Mallory ping both Alice and Bob - at some point he should
            # send a message to Alice encrypted with Mallory-Bob session key
            mallory.ping_peers(),
        ),
        timeout,
    )


def test_bad_message_format():
    """Test sending OLM prekey message in an established session."""
    with pytest.raises(SessionErrorOkException):
        asyncio.get_event_loop().run_until_complete(
            impl_test_bad_message_format()
        )
