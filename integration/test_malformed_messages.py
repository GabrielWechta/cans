"""Test server recovery from malformed upstream messages."""

import asyncio
import logging
import os
from json import JSONEncoder
from typing import Callable, Set

import pytest
import websockets.client as ws
from olm import Account
from websockets.exceptions import ConnectionClosed

from client import Client
from client.session_manager_client import SessionManager
from common.connection import CansStatusCode
from common.keys import EcPemKeyPair, digest_key, generate_keys
from common.messages import CansMessage, CansMsgId, cans_send


class MockSessionManager(SessionManager):
    """Session manager that allows overriding selected methods."""

    def __init__(
        self,
        keys: EcPemKeyPair,
        account: Account,
        run_server_handshake_override: Callable = None,
        handle_upstream_override: Callable = None,
    ) -> None:
        """Construct a mockable session manager."""
        super().__init__(keys, account)
        self.run_server_handshake_override = run_server_handshake_override
        self.handle_upstream_override = handle_upstream_override

    async def _run_server_handshake(
        self, conn: ws.WebSocketClientProtocol, friends: Set[str]
    ) -> None:
        """Shake hands with the server."""
        if self.run_server_handshake_override:
            await self.run_server_handshake_override(
                self=self, conn=conn, friends=friends
            )
        else:
            await super()._run_server_handshake(conn, friends)

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle upstream traffic, i.e. client to server."""
        if self.handle_upstream_override:
            await self.handle_upstream_override(self, conn)
        else:
            await super()._handle_upstream(conn)


class MockClient(Client):
    """Mock client."""

    def __init__(
        self,
        keys: EcPemKeyPair,
        run_server_handshake_override: Callable = None,
        handle_upstream_override: Callable = None,
    ) -> None:
        """Construct mock client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.event_loop = asyncio.get_event_loop()
        self._do_logger_config()

        self.log = logging.getLogger("cans-logger")
        self.log.setLevel(logging.DEBUG)

        account = Account()
        self.session_manager = MockSessionManager(
            keys=keys,
            account=account,
            run_server_handshake_override=run_server_handshake_override,
            handle_upstream_override=handle_upstream_override,
        )

    def run(self) -> None:
        """Run dummy client application. Do not try handling exceptions."""
        self.event_loop.run_until_complete(
            self.session_manager.connect(
                url=f"wss://{self.server_hostname}:{self.server_port}",
                certpath=self.certpath,
                friends=set(),
            ),
        )


def test_deserialization_error_in_handshake():
    """Test recovery from deserialization failure during handshake."""
    # Define mock handshake runner which sends malformed data
    async def handshake_override(
        self, conn: ws.WebSocketClientProtocol, friends: Set[str]
    ) -> None:
        """Send non-deserializable data during handshake."""
        await conn.send(bytes([i for i in range(64)]))

    # Instantiate a mock client which overrides the handshake method
    alice = MockClient(generate_keys(), handshake_override)

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"


def test_malformed_header_in_handshake():
    """Test recovery from a malformed CANS header during handshake."""
    # Define mock handshake runner which sends malformed data
    async def handshake_override(
        self, conn: ws.WebSocketClientProtocol, friends: Set[str]
    ) -> None:
        """Send deserializable but still malformed message during handshake."""
        serialized = JSONEncoder().encode(
            {"dummy": 42, "payload": {"text": "Hello world"}}
        )
        await conn.send(serialized)

    # Instantiate a mock client which overrides the handshake method
    alice = MockClient(generate_keys(), handshake_override)

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"


def test_malformed_payload_in_handshake():
    """Test recovery from a malformed CANS payload during handshake."""
    # Define mock handshake runner which sends malformed data
    async def handshake_override(
        self, conn: ws.WebSocketClientProtocol, friends: Set[str]
    ) -> None:
        """Send a CANS message with unexpected payload during handshake."""
        message = CansMessage()
        message.header.receiver = None
        message.header.sender = self.identity
        message.header.msg_id = CansMsgId.SCHNORR_COMMIT
        message.payload = {
            "dummy": 42,
        }
        await cans_send(message, conn)

    # Instantiate a mock client which overrides the handshake method
    alice = MockClient(generate_keys(), handshake_override)

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"


def test_deserialization_error_in_session():
    """Test recovery from deserialization failure in an established session."""
    # Define mock upstream handler which sends malformed data
    async def upstream_override(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Send non-deserializable data in a well-established session."""
        await conn.send(bytes([i for i in range(64)]))

    # Instantiate a mock client which overrides the upstream handler
    alice = MockClient(
        keys=generate_keys(),
        run_server_handshake_override=None,
        handle_upstream_override=upstream_override,
    )

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"


def test_malformed_header_in_session():
    """Test recovery from a malformed CANS header in an established session."""
    # Define mock upstream handler which sends malformed data
    async def upstream_override(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Send deserializable but still malformed message in a session."""
        serialized = JSONEncoder().encode(
            {"dummy": 42, "payload": {"text": "Hello world"}}
        )
        await conn.send(serialized)

    # Instantiate a mock client which overrides the upstream handler
    alice = MockClient(
        keys=generate_keys(),
        run_server_handshake_override=None,
        handle_upstream_override=upstream_override,
    )

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"


def test_malformed_payload_in_session():
    """Test recovery from a malformed CANS payload in a session."""
    # Define mock upstream handler which sends malformed data
    async def upstream_override(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Send a CANS message with unexpected payload in a session."""
        message = CansMessage()
        message.header.receiver = None
        message.header.sender = self.identity
        message.header.msg_id = CansMsgId.REQUEST_LOGOUT_NOTIF
        message.payload = {
            "dummy": 42,
        }
        await cans_send(message, conn)

    # Instantiate a mock client which overrides the upstream handler
    alice = MockClient(
        keys=generate_keys(),
        run_server_handshake_override=None,
        handle_upstream_override=upstream_override,
    )

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"


def test_impersonation_attempt():
    """Test detection of a naive impersonation attempt."""
    # Define mock upstream handler which attempts impersonation
    async def upstream_override(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Try impersonating another user."""
        # Fill in the sender field with someone else's user ID
        sender = digest_key(generate_keys()[1])
        message = CansMessage()
        message.header.receiver = None
        message.header.sender = sender
        message.header.msg_id = CansMsgId.REQUEST_LOGOUT_NOTIF
        await cans_send(message, conn)

    # Instantiate a mock client which overrides the upstream handler
    alice = MockClient(
        keys=generate_keys(),
        run_server_handshake_override=None,
        handle_upstream_override=upstream_override,
    )

    # Expect connection dropped by the server
    with pytest.raises(ConnectionClosed) as excinfo:
        alice.run()
    assert (
        excinfo.value.code == CansStatusCode.MALFORMED_MESSAGE
    ), "Invalid status code"
