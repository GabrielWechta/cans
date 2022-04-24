"""Clientside session manager."""

import asyncio
import logging
import ssl
from typing import Dict, List

import websockets.client as ws
from olm import Account, OlmMessage, OlmPreKeyMessage

from common.keys import KeyPair, PubKeyDigest, digest_key
from common.messages import (
    ActiveFriends,
    CansMessage,
    CansMsgId,
    ReplenishOneTimeKeysResp,
    ServerHello,
    UserMessage,
    cans_recv,
    cans_send,
)

from .e2e_encryption import DoubleRatchetSession, TripleDiffieHellmanInterface


class ActiveSession(DoubleRatchetSession):
    """Interface for SessionManager convenience."""

    pass


class PotentialSession:
    """Utility mapping friends pub_keys on (id_keys, ot_keys)."""

    def __init__(self, identity_key: str, one_time_key: str):
        """Construct easy way of finding public bundle."""
        self.identity_key = identity_key
        self.one_time_key = one_time_key


class SessionManager:
    """Session manager.

    Manage a session with the server, listen for server
    events and forward user messages to the server.
    """

    def __init__(
        self,
        keys: KeyPair,
        account: Account,
    ) -> None:
        """Construct a session manager instance."""
        self.account = account
        self.tdh_interface = TripleDiffieHellmanInterface(account=self.account)
        self.active_sessions: Dict[PubKeyDigest, ActiveSession] = {}
        self.potential_sessions: Dict[PubKeyDigest, PotentialSession] = {}

        self.public_key, self.private_key = keys
        self.identity = digest_key(keys[0])

        self.log = logging.getLogger("cans-logger")

        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self._handle_message_user,
            CansMsgId.PEER_UNAVAILABLE: self._handle_message_peer_unavailable,
            CansMsgId.PEER_LOGIN: self._handle_message_peer_login,
            CansMsgId.PEER_LOGOUT: self._handle_message_peer_logout,
            # fmt: off
            CansMsgId.REPLENISH_ONE_TIME_KEYS_REQ:
                self._handle_message_replenish_one_time_keys_req,
            # fmt: on
        }
        self.upstream_message_queue: asyncio.Queue = asyncio.Queue()
        self.downstream_user_message_queue: asyncio.Queue = asyncio.Queue()
        self.downstream_system_message_queue: asyncio.Queue = asyncio.Queue()

    async def connect(
        self, url: str, certpath: str, friends: List[PubKeyDigest]
    ) -> None:
        """Connect to the server."""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Trust the self-signed certificate and ignore hostname
        # - all for PoC purposes only
        ssl_context.load_verify_locations(certpath)
        ssl_context.check_hostname = False

        self.log.debug(f"Connecting to the server at {url}...")

        async with ws.connect(url, ssl=ssl_context) as conn:
            self.log.debug(
                "Successfully connected to the server. Running handshake..."
            )
            await self._run_server_handshake(conn, friends)
            self.log.debug(
                "Handshake complete. Forking to handle"
                + " upstream and downstream concurrently..."
            )
            await asyncio.gather(
                self._handle_upstream(conn),
                self._handle_downstream(conn),
            )

    async def send_message(self, message: CansMessage) -> None:
        """Send an outgoing message."""
        await self.upstream_message_queue.put(message)

    async def receive_user_message(self) -> CansMessage:
        """Wait for an incoming user message."""
        return await self.downstream_user_message_queue.get()

    async def receive_system_message(self) -> CansMessage:
        """Wait for an incoming system notification."""
        return await self.downstream_system_message_queue.get()

    def user_message_to(self, peer: PubKeyDigest, payload: str) -> UserMessage:
        """Create a user message to a peer."""
        message = UserMessage(peer, payload)
        message.header.sender = self.identity
        return message

    async def _run_server_handshake(
        self, conn: ws.WebSocketClientProtocol, friends: List[PubKeyDigest]
    ) -> None:
        """Shake hands with the server."""
        # Send server hello
        identity_key = self.account.identity_keys["curve25519"]
        one_time_keys = self.tdh_interface.get_one_time_keys(3)
        hello = ServerHello(
            public_key=self.public_key,
            subscriptions=friends,
            identity_key=identity_key,
            one_time_keys=one_time_keys,
        )
        await cans_send(hello, conn)

        # Receive the active friends list
        active_friends_message: ActiveFriends = await cans_recv(conn)

        # Create potential sessions with active friends
        for (
            pub_key_digest,
            public_key_bundle,
        ) in active_friends_message.payload["friends"].items():
            identity_key, one_time_key = public_key_bundle
            self.potential_sessions[pub_key_digest] = PotentialSession(
                identity_key=identity_key, one_time_key=one_time_key
            )

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = await self.upstream_message_queue.get()
            receiver = message.header.receiver

            # Currently receiver being None means the message should be
            # terminated by the server
            if receiver is not None:
                if receiver in self.potential_sessions.keys():
                    self._activate_outbound_session(receiver)

                if receiver in self.active_sessions.keys():
                    message = self._encrypt_user_payload(message)

            await cans_send(message, conn)

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
                self.log.warning(
                    "Received unexpected message with ID:"
                    + f"{message.header.msg_id}"
                )

    async def _handle_message_user(self, message: CansMessage) -> None:
        """Handle message type USER_MESSAGE."""
        sender = message.header.sender

        if sender in self.active_sessions.keys():
            message = self._decrypt_user_payload(message)
            await self.downstream_user_message_queue.put(message)
        else:
            self._activate_inbound_session(message)
            message = self._decrypt_user_payload_prekey(message)
            await self.downstream_user_message_queue.put(message)

    async def _handle_message_peer_unavailable(
        self, message: CansMessage
    ) -> None:
        """Handle message type PEER_UNAVAILABLE."""
        peer = message.payload["peer"]

        # TODO-UI implement behaviour of peer unavailable
        self.log.warning(f"Peer {peer} unavailable!")
        await self.downstream_system_message_queue.put(message)

    async def _handle_message_peer_login(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGIN."""
        peer = message.payload["peer"]
        identity_key, one_time_key = message.payload["public_keys_bundle"]
        self.potential_sessions[peer] = PotentialSession(
            identity_key=identity_key, one_time_key=one_time_key
        )

        # TODO-UI implement behaviour of user login
        self.log.info(f"Peer {peer} just logged in!")
        await self.downstream_system_message_queue.put(message)

    async def _handle_message_peer_logout(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGOUT."""
        peer = message.payload["peer"]

        if peer in self.potential_sessions.keys():
            self.potential_sessions.pop(peer)
        elif peer in self.active_sessions.keys():
            self.active_sessions.pop(peer)

        # TODO-UI implement behaviour of user logout
        self.log.info(f"Peer {peer} just logged out!")
        await self.downstream_system_message_queue.put(message)

    async def _handle_message_replenish_one_time_keys_req(
        self, message: CansMessage
    ) -> None:
        """Handle message type REPLENISH_ONE_TIME_KEYS_REQ."""
        one_time_keys_num = message.payload["one_time_keys_num"]

        # one time keys are right away marked as published
        one_time_keys = self.tdh_interface.get_one_time_keys(
            number_of_keys=one_time_keys_num
        )
        rep_otk_resp = ReplenishOneTimeKeysResp(one_time_keys=one_time_keys)
        await self.upstream_message_queue.put(rep_otk_resp)

    def _activate_outbound_session(self, peer: PubKeyDigest) -> None:
        """Transform potential session into an active outbound session."""
        self.log.debug(f"Activating outbound session with {peer}...")
        # Remove entry from potential sessions
        potential_session = self.potential_sessions.pop(peer)
        # Transform potential session to active session
        active_session = ActiveSession(account=self.account)
        active_session.start_outbound_session(
            peer_id_key=potential_session.identity_key,
            peer_one_time_key=potential_session.one_time_key,
        )
        # Store new active session
        self.active_sessions[peer] = active_session

    def _activate_inbound_session(self, message: CansMessage) -> None:
        """Activate an inbound session based on a received prekey message."""
        peer = message.header.sender
        self.log.debug(f"Activating inbound session with {peer}...")
        prekey_message = OlmPreKeyMessage(message.payload)
        # Remove peer from potential sessions if present
        if peer in self.potential_sessions:
            self.potential_sessions.pop(peer)
        # Activate a new session
        active_session = ActiveSession(account=self.account)
        active_session.start_inbound_session(prekey_message)
        # Store new active session
        self.active_sessions[peer] = active_session

    def _encrypt_user_payload(self, message: CansMessage) -> CansMessage:
        """Encrypt the payload of a user message."""
        olm_message = self.active_sessions[message.header.receiver].encrypt(
            message.payload
        )
        message.payload = olm_message.ciphertext
        return message

    def _decrypt_user_payload(self, message: CansMessage) -> CansMessage:
        """Decrypt the payload of a user message."""
        olm_message = OlmMessage(message.payload)
        message.payload = self.active_sessions[message.header.sender].decrypt(
            olm_message
        )
        return message

    def _decrypt_user_payload_prekey(
        self, message: CansMessage
    ) -> CansMessage:
        """Decrypt user message wrapped in a prekey olm message."""
        prekey_message = OlmPreKeyMessage(message.payload)
        session = self.active_sessions[message.header.sender]
        message.payload = session.decrypt(prekey_message)
        return message
