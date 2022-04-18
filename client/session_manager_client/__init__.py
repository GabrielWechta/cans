"""Clientside session manager."""

import asyncio  # TODO: Most likely also not needed
import logging
import ssl
import sys  # TODO: Not needed after PoC

import websockets.client as ws
from key_manager import KeyManager

from common.keys import PubKeyDigest
from common.messages import (
    CansMsgId,
    ServerHello,
    UserMessage,
    cans_recv,
    cans_send,
)
from common.messages.messages import CansMessage


class SessionManager:
    """Session manager.

    Manage a session with the server, listen for server
    events and forward user messages to the server.
    """

    def __init__(self, key_manager: KeyManager) -> None:
        """Construct a session manager instance."""
        self.key_manager = key_manager
        # TODO: Implement client-side logging
        self.log = logging.getLogger("cans-logger")

        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self.__handle_message_user,
            CansMsgId.PEER_UNAVAILABLE: self.__handle_message_peer_unavailable,
            CansMsgId.PEER_LOGIN: self.__handle_message_peer_login,
            CansMsgId.PEER_LOGOUT: self.__handle_message_peer_logout,
            CansMsgId.ACTIVE_FRIENDS: self.__handle_message_active_friends,
        }

    async def connect(self, url: str) -> None:
        """Connect to the server."""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.load_verify_locations(
            # Trust the self-signed certificate for PoC purposes
            "certs/CansCert.pem"
        )

        async with ws.connect(url, ssl=ssl_context) as conn:
            await asyncio.gather(
                self.__handle_upstream(conn), self.__handle_downstream(conn)
            )

    async def __handle_upstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Handle upstream traffic, i.e. client to server."""
        public_key = self.key_manager.get_own_public_key_digest()
        peer_key = sys.argv[2]

        if "Alice" in public_key:
            # Test peer unavailable and login notifications
            await asyncio.sleep(5)

        # Say hello to the server
        hello = ServerHello(public_key, [peer_key])
        await cans_send(hello, conn)

        while True:
            request = self.__user_message_to(peer_key)
            request.payload = f"Hello {peer_key}, this is {public_key}"
            await cans_send(request, conn)
            await asyncio.sleep(3)

    async def __handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Handle downstream traffic, i.e. server to client."""
        while True:
            message = await cans_recv(conn)

            if message.header.msg_id in self.message_handlers.keys():
                # Call a registered handler
                await self.message_handlers[message.header.msg_id](message)
            else:
                print(
                    "Received unexpected message with ID:"
                    + f"{message.header.msg_id}"
                )

    async def __handle_message_user(self, message: CansMessage) -> None:
        """Handle message type USER_MESSAGE."""
        print(
            f"Received user message {message.payload} from"
            + f" {message.header.sender}"
        )

    async def __handle_message_peer_unavailable(
        self, message: CansMessage
    ) -> None:
        """Handle message type PEER_UNAVAILABLE."""
        peer = message.payload["peer"]
        print(f"Peer {peer} unavailable!")

    async def __handle_message_peer_login(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGIN."""
        peer = message.payload["peer"]
        print(f"Peer {peer} just logged in!")

    async def __handle_message_peer_logout(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGOUT."""
        peer = message.payload["peer"]
        print(f"Peer {peer} just logged out!")

    async def __handle_message_active_friends(
        self, message: CansMessage
    ) -> None:
        """Handle message type ACTIVE_FRIENDS."""
        friends = message.payload["friends"]
        print(f"Active friends: {friends}")

    def __user_message_to(self, peer: PubKeyDigest) -> UserMessage:
        """Create a user message to a peer."""
        message = UserMessage(peer)
        message.header.sender = self.key_manager.get_own_public_key_digest()
        return message
