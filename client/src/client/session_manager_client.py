"""Clientside session manager."""

import asyncio
import logging
import ssl

import websockets.client as ws
from olm import Account, OlmPreKeyMessage, OlmMessage

from common.keys import PubKeyDigest
from common.messages import (
    CansMessage,
    CansMsgId,
    ServerHello,
    UserMessage,
    cans_recv,
    cans_send, ActiveFriends,
)

from .e2e_encryption import TripleDiffieHellmanInterface, DoubleRatchetSession
from .key_manager import KeyManager


class ActiveSession(DoubleRatchetSession):
    pass


class PotentialSession:
    def __init__(self, identity_key: str, one_time_key: str):
        self.identity_key = identity_key
        self.one_time_key = one_time_key


class SessionManager:
    """Session manager.

    Manage a session with the server, listen for server
    events and forward user messages to the server.
    """

    def __init__(
            self,
            key_manager: KeyManager,
            hardcoded_peer: PubKeyDigest,
            account: Account,
    ) -> None:
        """Construct a session manager instance."""
        self.account = account
        self.tdh_interface = TripleDiffieHellmanInterface(account=self.account)
        self.key_manager = key_manager
        self.active_sessions = {}
        self.potential_sessions = {}

        # TODO: Implement client-side logging
        self.log = logging.getLogger("cans-logger")

        # TODO: Remove after alpha presentation
        self.hardcoded_peer_key = hardcoded_peer

        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self._handle_message_user,
            CansMsgId.PEER_UNAVAILABLE: self._handle_message_peer_unavailable,
            CansMsgId.PEER_LOGIN: self._handle_message_peer_login,
            CansMsgId.PEER_LOGOUT: self._handle_message_peer_logout,
        }

    async def connect(self, url: str, certpath: str) -> None:
        """Connect to the server."""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Trust the self-signed certificate and ignore hostname
        # - all for PoC purposes only
        ssl_context.load_verify_locations(certpath)
        ssl_context.check_hostname = False

        async with ws.connect(url, ssl=ssl_context) as conn:
            public_key = self.key_manager.get_own_public_key_digest()

            if "Alice" in public_key:
                # Test peer unavailable and login notifications
                print("Alice lagging behind a bit...")
                await asyncio.sleep(3)

            # Say hello to the server
            identity_key = self.account.identity_keys["curve25519"]
            one_time_keys = self.tdh_interface.get_one_time_keys(3)
            hello = ServerHello(public_key=public_key,
                                subscriptions=[self.hardcoded_peer_key],
                                identity_key=identity_key,
                                one_time_keys=one_time_keys)

            await cans_send(hello, conn)

            # For sure this message is ActiveFriends.
            active_friends_message: ActiveFriends = await cans_recv(conn)

            for pub_key_digest, public_key_bundle in \
                    active_friends_message.payload["friends"].items():
                identity_key, one_time_key = public_key_bundle
                self.potential_sessions[pub_key_digest] = PotentialSession(
                    identity_key=identity_key, one_time_key=one_time_key)

            await asyncio.gather(
                self._handle_upstream(conn), self._handle_downstream(conn)
            )

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle upstream traffic, i.e. client to server."""
        public_key = self.key_manager.get_own_public_key_digest()

        while True:
            dummy_message = self._user_message_to(self.hardcoded_peer_key)
            plaintext = f"Hello {self.hardcoded_peer_key}, this is {public_key}"
            receiver = dummy_message.header.receiver

            if receiver in self.potential_sessions.keys():
                potential_session = self.potential_sessions.pop(receiver)
                identity_key, one_time_key = potential_session.identity_key, potential_session.one_time_key
                active_session = ActiveSession(account=self.account)
                active_session.start_outbound_session(peer_id_key=identity_key,
                                                      peer_one_time_key=one_time_key)
                self.active_sessions[receiver] = active_session

            if receiver in self.active_sessions.keys():
                pre_key_message = self.active_sessions[receiver].encrypt(
                    plaintext)
                dummy_message.payload = pre_key_message.ciphertext

            await cans_send(dummy_message, conn)
            await asyncio.sleep(2)

    async def _handle_downstream(
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

    async def _handle_message_user(self, message: CansMessage) -> None:
        """Handle message type USER_MESSAGE."""
        sender = message.header.sender
        ciphertext = message.payload

        if sender in self.potential_sessions.keys():
            pre_key_message = OlmPreKeyMessage(ciphertext)
            self.potential_sessions.pop(sender)
            active_session = ActiveSession(account=self.account)
            active_session.start_inbound_session(pre_key_message)
            self.active_sessions[sender] = active_session
            plaintext = self.active_sessions[sender].decrypt(pre_key_message)
            print(
                f"Received encrypted user message {ciphertext} from"
                + f" {message.header.sender} that decrypted to {plaintext}.")
        elif sender in self.active_sessions.keys():
            olm_message = OlmMessage(ciphertext)
            plaintext = self.active_sessions[sender].decrypt(olm_message)
            print(
                f"Received encrypted user message {ciphertext} from"
                + f" {message.header.sender} that decrypted to {plaintext}.")
        else:
            # TODO implement behaviour of new user message while doing UI
            print("User message from the other side of the moon.")

    async def _handle_message_peer_unavailable(
            self, message: CansMessage
    ) -> None:
        """Handle message type PEER_UNAVAILABLE."""
        peer = message.payload["peer"]
        print(f"Peer {peer} unavailable!")

    async def _handle_message_peer_login(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGIN."""
        peer = message.payload["peer"]
        identity_key, one_time_key = message.payload["public_keys_bundle"]
        self.potential_sessions[peer] = PotentialSession(
            identity_key=identity_key, one_time_key=one_time_key)

        print(f"Peer {peer} just logged in!")

    async def _handle_message_peer_logout(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGOUT."""
        # TODO: Clean up peer session (self.active_sessions.pop())
        peer = message.payload["peer"]
        print(f"Peer {peer} just logged out!")

    def _user_message_to(self, peer: PubKeyDigest) -> UserMessage:
        """Create a user message to a peer."""
        message = UserMessage(peer)
        message.header.sender = self.key_manager.get_own_public_key_digest()
        return message
