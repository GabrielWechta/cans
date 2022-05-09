"""Clientside session manager."""

import asyncio
import logging
import ssl
from typing import List

import websockets.client as ws
from olm import Account, OlmMessage

from common.keys import KeyPair, PubKeyDigest, digest_key
from common.messages import (
    ActiveFriends,
    CansMessage,
    CansMsgId,
    PeerHello,
    ReplenishOneTimeKeysResp,
    ServerHello,
    SessionEstablished,
    UserMessage,
    cans_recv,
    cans_send,
)

from .e2e_encryption import TripleDiffieHellmanInterface
from .sessions_state_machine import SessionsStateMachine


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
        self.state_machine = SessionsStateMachine(account=self.account)

        self.public_key, self.private_key = keys
        self.identity = digest_key(keys[0])

        self.log = logging.getLogger("cans-logger")

        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self._handle_message_user_message,
            CansMsgId.PEER_HELLO: self._handle_message_peer_hello,
            CansMsgId.PEER_UNAVAILABLE: self._handle_message_peer_unavailable,
            CansMsgId.PEER_LOGIN: self._handle_message_peer_login,
            CansMsgId.PEER_LOGOUT: self._handle_message_peer_logout,
            # fmt: off
            CansMsgId.REPLENISH_ONE_TIME_KEYS_REQ:
                self._handle_message_replenish_one_time_keys_req,
            CansMsgId.SESSION_ESTABLISHED:
                self._handle_message_session_established,
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
        one_time_keys = self.tdh_interface.get_one_time_keys(10)
        hello = ServerHello(
            public_key=self.public_key,
            subscriptions=friends,
            identity_key=identity_key,
            one_time_keys=one_time_keys,
        )
        hello.sender = self.identity
        await cans_send(hello, conn)

        # Receive the active friends list
        active_friends_message: ActiveFriends = await cans_recv(conn)

        # Create potential sessions with active friends
        for (
            pub_key_digest,
            public_key_bundle,
        ) in active_friends_message.payload["friends"].items():
            identity_key, one_time_key = public_key_bundle
            self.state_machine.add_potential_session(
                peer=pub_key_digest,
                identity_key=identity_key,
                one_time_key=one_time_key,
            )

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = await self.upstream_message_queue.get()
            receiver = message.header.receiver

            if receiver is None:
                # Receiver is None - the message should be terminated by
                # the server and so no crypto session is used
                await cans_send(message, conn)
            elif receiver in self.state_machine.potential_sessions.keys():
                # Session not yet established, buffer the user message
                # and initiate the key exchange
                self.log.debug(
                    f"Sending first message to peer {receiver}. Buffering the"
                    + " user message and sending PEER_HELLO first..."
                )
                self.state_machine.make_session_pending(receiver, message)
                # Send a hello message first
                message = PeerHello(receiver)
                message.header.sender = self.identity
                message = self._encrypt_user_payload(message)
                await cans_send(message, conn)
                # The buffered user message will be sent as soon as session
                # is established
            elif receiver in self.state_machine.pending_sessions.keys():
                self.log.warning(
                    f"Buffering new message to peer {receiver}. Session still"
                    + " not established"
                )
                # Still waiting for ACK, buffer the message
                self.state_machine.pend_message(receiver, message)
            elif receiver in self.state_machine.active_sessions.keys():
                # Well-established session, encrypt the payload
                message = self._encrypt_user_payload(message)
                await cans_send(message, conn)
            else:
                self.log.error(
                    "Internal error. Tried sending message"
                    + f" {message.header.msg_id} to an unknown receiver"
                    + f" {message.header.receiver}"
                )

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

    async def _resolve_race_condition(
        self, hello_message: CansMessage
    ) -> None:
        """Resolve an outbound session conflict."""
        peer = hello_message.header.sender
        # Decide based on the public ID which party should submit
        if self.identity < peer:
            self.log.info(
                f"Forfeiting pending outbound session with peer {peer}"
                + " and accepting inbound session..."
            )
            # Forfeit the outbound session and accept an inbound session
            self.state_machine.activate_inbound_session(hello_message)
            # Send ACK to the other party
            await self.__acknowledge_peer_session(peer)

    async def __acknowledge_peer_session(self, peer: PubKeyDigest) -> None:
        """Send an session established acknowledgement to the peer."""
        acknowledge = SessionEstablished(peer)
        acknowledge.header.sender = self.identity
        await self.send_message(acknowledge)

    async def _handle_message_user_message(self, message: CansMessage) -> None:
        """Handle message type USER_MESSAGE."""
        sender = message.header.sender

        if sender in self.state_machine.active_sessions.keys():
            message = self._decrypt_user_payload(message)
            await self.downstream_user_message_queue.put(message)
        else:
            self.log.warning(
                f"Dropping a user message from {sender}! No active session!"
            )

    async def _handle_message_peer_hello(self, message: CansMessage) -> None:
        """Handle message type PEER_HELLO."""
        peer = message.header.sender
        self.log.debug(f"Handling PEER_HELLO message from {peer}...")

        if peer in self.state_machine.potential_sessions.keys():
            # Activate an inbound session
            self.state_machine.activate_inbound_session(message)
            # Send ACK to the other party
            await self.__acknowledge_peer_session(peer)
        elif peer in self.state_machine.pending_sessions.keys():
            # Race condition! Both parties started outbound sessions
            # at the same time!
            self.log.info(
                f"Outbound session conflict occurred with peer {peer}"
            )
            # TODO: Add max number of retries
            await self._resolve_race_condition(message)
        elif peer in self.state_machine.active_sessions.keys():
            self.log.error(
                "Internal error! Received PEER_HELLO"
                + f" from an active peer: {peer}"
            )
        else:
            # Hello from a new user
            self.log.debug(f"Received PEER_HELLO from an unknown user: {peer}")
            # Activate an inbound session
            self.state_machine.activate_inbound_session(message)
            # Send ACK to the other party
            await self.__acknowledge_peer_session(peer)
            # TODO-UI: Implement handling of new users

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
        self.state_machine.add_potential_session(
            peer=peer,
            identity_key=identity_key,
            one_time_key=one_time_key,
        )

        # TODO-UI implement behaviour of user login
        self.log.info(f"Peer {peer} just logged in!")
        await self.downstream_system_message_queue.put(message)

    async def _handle_message_peer_logout(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGOUT."""
        peer = message.payload["peer"]
        self.state_machine.terminate_session(peer)

        # TODO-UI implement behaviour of user logout
        self.log.info(f"Peer {peer} just logged out!")
        await self.downstream_system_message_queue.put(message)

    async def _handle_message_replenish_one_time_keys_req(
        self, message: CansMessage
    ) -> None:
        """Handle message type REPLENISH_ONE_TIME_KEYS_REQ."""
        one_time_keys_num = message.payload["count"]

        # one time keys are right away marked as published
        one_time_keys = self.tdh_interface.get_one_time_keys(
            number_of_keys=one_time_keys_num
        )
        rep_otk_resp = ReplenishOneTimeKeysResp(one_time_keys=one_time_keys)
        rep_otk_resp.sender = self.identity
        await self.send_message(rep_otk_resp)

    async def _handle_message_session_established(
        self, message: CansMessage
    ) -> None:
        """Handle message type SESSION_ESTABLISHED."""
        peer = message.header.sender
        self.log.debug(
            f"Handling message SESSION_ESTABLISHED from peer {peer}..."
        )
        # Get pending messages
        pending_messages = self.state_machine.flush_pending_session(peer)
        # Mark session as active
        self.state_machine.mark_outbound_session_active(message)

        # Send the pending messages
        for message in pending_messages:
            await self.send_message(message)

    def _encrypt_user_payload(self, message: CansMessage) -> str:
        """Encrypt the payload of a user message."""
        receiver = message.header.receiver
        encrypt = self.state_machine.get_encryption_callback(receiver)
        olm_message = encrypt(message.payload)
        message.payload = olm_message.ciphertext
        return message

    def _decrypt_user_payload(self, message: CansMessage) -> str:
        """Decrypt the payload of a user message."""
        sender = message.header.sender
        decrypt = self.state_machine.get_decryption_callback(sender)
        olm_message = OlmMessage(message.payload)
        message.payload = decrypt(olm_message)
        return message
