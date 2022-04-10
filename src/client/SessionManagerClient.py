"""Clientside session manager."""

import asyncio  # TODO: Most likely also not needed
import logging
import ssl
import sys  # TODO: Not needed after PoC

import websockets.client as ws
from KeyManager import KeyManager

from common.keys.PubKeyDigest import PubKeyDigest
from common.messages.CansMsgId import CansMsgId
from common.messages.MessageApi import cans_recv, cans_send
from common.messages.ServerHello import ServerHello
from common.messages.UserMessage import UserMessage


class SessionManagerClient:
    """Session manager.

    Manage a session with the server, listen for server
    events and forward user messages to the server.
    """

    def __init__(self, key_manager: KeyManager) -> None:
        """Construct a session manager instance."""
        self.key_manager = key_manager
        # TODO: Implement client-side logging
        self.log = logging.getLogger("cans-logger")

    async def connect(self, url: str) -> None:
        """Connect to the server."""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.load_verify_locations(
            # Trust the self-signed certificate for PoC purposes
            "certs/CansCert.pem"
        )

        async with ws.connect(url, ssl=ssl_context) as conn:
            # TODO: Run the actual client
            await self.__dummy_poc_client(conn)

    async def __dummy_poc_client(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Run dummy client implementation."""
        # NOTE: For PoC purposes get a mock public_key
        # from the command line
        public_key = self.key_manager.get_own_public_key_digest()
        peer_key = sys.argv[2]

        if "Alice" in public_key:
            # Test "peer unavailable" condition
            await asyncio.sleep(5)

        # Say hello to the server
        hello = ServerHello()
        hello.payload["public_key"] = public_key
        await cans_send(hello, conn)

        while True:
            request = self.user_message_to(peer_key)
            request.payload = f"Hello {peer_key}, this is {public_key}"
            await cans_send(request, conn)

            response = await cans_recv(conn)

            if response.header.sender != "":
                print(
                    f"Received message '{response.payload}' from"
                    + f" {response.header.sender}"
                )
            elif response.header.msg_id == CansMsgId.PEER_UNAVAILABLE:
                print(f"Peer {peer_key} is unavailable")
            else:
                print(
                    "Received unexpected message with ID:"
                    + f"{response.header.msg_id}"
                )

            await asyncio.sleep(1)

    def user_message_to(self, peer: PubKeyDigest) -> UserMessage:
        """Create a user message to a peer."""
        message = UserMessage(peer)
        message.header.sender = self.key_manager.get_own_public_key_digest()
        return message
