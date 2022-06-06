"""Clientside session manager."""

import asyncio
import logging
import ssl
from typing import Set, Tuple

import websockets.client as ws
from olm import Account, OlmMessage

from common.keys import (
    EcPemKeyPair,
    digest_key,
    get_private_key_from_pem,
    get_schnorr_commitment,
    get_schnorr_response,
)
from common.messages import (
    ActiveFriends,
    AddFriend,
    CansMessage,
    CansMessageException,
    CansMsgId,
    PeerHello,
    ReplenishOneTimeKeysResp,
    RequestLogoutNotif,
    SchnorrChallenge,
    SchnorrCommit,
    SchnorrResponse,
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
        keys: EcPemKeyPair,
        account: Account,
    ) -> None:
        """Construct a session manager instance."""
        self.log = logging.getLogger("cans-logger")
        self.account = account
        self.tdh_interface = TripleDiffieHellmanInterface(account=self.account)
        self.session_sm = SessionsStateMachine(account=self.account)

        self.private_key = get_private_key_from_pem(keys[0])
        self.public_key = keys[1]
        self.identity = digest_key(keys[1])

        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self._handle_message_user_message,
            CansMsgId.PEER_HELLO: self._handle_message_peer_hello,
            CansMsgId.PEER_LOGIN: self._handle_message_peer_login,
            CansMsgId.PEER_LOGOUT: self._handle_message_peer_logout,
            # fmt: off
            CansMsgId.ACK_MESSAGE_DELIVERED:
                self.__handle_message_ack_message_delivered,
            CansMsgId.NACK_MESSAGE_NOT_DELIVERED:
                self.__handle_message_nack_message_not_delivered,
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
        self, url: str, certpath: str, friends: Set[str]
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

    async def receive_user_message(self) -> UserMessage:
        """Wait for an incoming user message."""
        return await self.downstream_user_message_queue.get()

    async def receive_system_message(self) -> CansMessage:
        """Wait for an incoming system notification."""
        return await self.downstream_system_message_queue.get()

    async def add_friend(self, peer: str) -> None:
        """Add new friend."""
        # Send a request to the server
        request = AddFriend(peer)
        await self.send_message(request)

    def user_message_to(
        self, peer: str, payload: str
    ) -> Tuple[UserMessage, str]:
        """Create a user message to a peer."""
        message = UserMessage(peer, payload)
        return message, message.payload["cookie"]

    async def _run_server_handshake(
        self, conn: ws.WebSocketClientProtocol, friends: Set[str]
    ) -> None:
        """Shake hands with the server."""
        # Send Schnorr commitment
        secret_ephemeral, public_ephemeral = get_schnorr_commitment()
        commit_message = SchnorrCommit(self.public_key, public_ephemeral)
        await cans_send(commit_message, conn)

        # Wait for the challenge
        challenge_message: SchnorrChallenge = await cans_recv(conn)
        challenge = challenge_message.payload["challenge"]

        # Send the response
        response = get_schnorr_response(
            private_key=self.private_key,
            ephemeral=secret_ephemeral,
            challenge=challenge,
        )
        identity_key = self.account.identity_keys["curve25519"]
        one_time_keys = self.tdh_interface.get_one_time_keys(10)
        response_message = SchnorrResponse(
            response=response,
            subscriptions=friends,
            identity_key=identity_key,
            one_time_keys=one_time_keys,
        )
        await cans_send(response_message, conn)

        # Receive the active friends list
        active_friends_message: ActiveFriends = await cans_recv(conn)

        # Create potential sessions with active friends
        for (
            pub_key_digest,
            public_key_bundle,
        ) in active_friends_message.payload["friends"].items():
            identity_key, one_time_key = public_key_bundle
            self.session_sm.add_potential_session(
                peer=pub_key_digest,
                identity_key=identity_key,
                one_time_key=one_time_key,
            )

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = await self.upstream_message_queue.get()
            await self._handle_outgoing_message(conn, message)

    async def _handle_outgoing_message(
        self, conn: ws.WebSocketClientProtocol, message: CansMessage
    ) -> None:
        """Handle an outgoing message."""
        # Fill in missing sender
        message.header.sender = self.identity
        receiver = message.header.receiver

        if receiver is None:
            # Receiver is None - the message should be terminated by
            # the server and so no crypto session is used
            await cans_send(message, conn)
        elif self.session_sm.potential_session_with(receiver):
            # Session not yet established, buffer the user message
            # and initiate the key exchange
            self.log.debug(
                f"Sending first message to peer {receiver}. Buffering the"
                + " user message and sending PEER_HELLO first..."
            )
            self.session_sm.make_session_pending(receiver, message)
            # Send a hello message first
            message = PeerHello(receiver)
            message.header.sender = self.identity
            message = self._encrypt_message_payload(message)
            await cans_send(message, conn)
            # The buffered user message will be sent as soon as session
            # is established
        elif self.session_sm.pending_session_with(receiver):
            self.log.warning(
                f"Buffering new message to peer {receiver}. Session still"
                + " not established"
            )
            # Still waiting for ACK, buffer the message
            self.session_sm.pend_message(receiver, message)
        elif self.session_sm.active_session_with(receiver):
            # Well-established session, encrypt the payload
            message = self._encrypt_message_payload(message)
            await cans_send(message, conn)
        else:
            self.log.warning(
                f"No active session with peer {message.header.receiver}"
            )

    async def _handle_downstream(
        self, conn: ws.WebSocketClientProtocol
    ) -> None:
        """Handle downstream traffic, i.e. server to client."""
        while True:
            message = await cans_recv(conn)
            try:
                await self._handle_incoming_message(conn, message)
            except (CansMessageException, AttributeError, KeyError) as e:
                self.log.error(f"{type(e).__name__}: {str(e)}")
                await self._handle_message_exception(
                    conn=conn, message=message, exception=e
                )

    async def _handle_incoming_message(
        self, conn: ws.WebSocketClientProtocol, message: CansMessage
    ) -> None:
        """Handle an incoming message."""
        if message.header.msg_id in self.message_handlers.keys():
            # Call a registered handler
            await self.message_handlers[message.header.msg_id](message)
        else:
            self.log.warning(
                "Received unexpected message with ID:"
                + f"{message.header.msg_id}"
            )

    async def _handle_message_exception(
        self,
        conn: ws.WebSocketClientProtocol,
        message: CansMessage,
        exception: Exception,
    ) -> None:
        """Handle a downstream message exception."""
        # TODO: Implement me!
        self.log.error("_handle_message_exception: Implement me!")
        pass

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
            self.session_sm.activate_inbound_session(hello_message)
            # Send ACK to the other party
            await self.__acknowledge_peer_session(peer)

    async def __acknowledge_peer_session(self, peer: str) -> None:
        """Send an session established acknowledgement to the peer."""
        acknowledge = SessionEstablished(peer)
        await self.send_message(acknowledge)

    async def _handle_message_user_message(self, message: CansMessage) -> None:
        """Handle message type USER_MESSAGE."""
        sender = message.header.sender

        if sender in self.session_sm.active_sessions.keys():
            message.payload["text"] = self._decrypt_text(
                sender, message.payload["text"]
            )
            await self.downstream_user_message_queue.put(message)
        else:
            self.log.warning(
                f"Dropping a user message from {sender}! No active session!"
            )

    async def _handle_message_peer_hello(self, message: CansMessage) -> None:
        """Handle message type PEER_HELLO."""
        peer = message.header.sender
        self.log.debug(f"Handling PEER_HELLO message from {peer}...")

        if peer in self.session_sm.potential_sessions.keys():
            # Activate an inbound session
            self.session_sm.activate_inbound_session(message)
            # Send ACK to the other party
            await self.__acknowledge_peer_session(peer)
        elif peer in self.session_sm.pending_sessions.keys():
            # Race condition! Both parties started outbound sessions
            # at the same time!
            self.log.info(
                f"Outbound session conflict occurred with peer {peer}"
            )
            # TODO: Add max number of retries
            await self._resolve_race_condition(message)
        elif peer in self.session_sm.active_sessions.keys():
            self.log.error(
                "Internal error! Received PEER_HELLO"
                + f" from an active peer: {peer}"
            )
        else:
            # Hello from a new user
            self.log.debug(f"Received PEER_HELLO from an unknown user: {peer}")
            # Activate an inbound session
            self.session_sm.activate_inbound_session(message)
            # Send ACK to the other party
            await self.__acknowledge_peer_session(peer)
            # Request notification from the server on the peer's logout
            notif_request = RequestLogoutNotif(peer)
            await self.send_message(notif_request)

    async def _handle_message_peer_login(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGIN."""
        peer = message.payload["peer"]
        identity_key, one_time_key = message.payload["public_keys_bundle"]
        self.session_sm.add_potential_session(
            peer=peer,
            identity_key=identity_key,
            one_time_key=one_time_key,
        )

        self.log.info(f"{peer} just logged in!")
        await self.downstream_system_message_queue.put(message)

    async def _handle_message_peer_logout(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGOUT."""
        peer = message.payload["peer"]
        self.session_sm.terminate_session(peer)

        self.log.info(f"{peer} just logged out!")
        await self.downstream_system_message_queue.put(message)

    async def __handle_message_ack_message_delivered(
        self, message: CansMessage
    ) -> None:
        """Handle message type ACK_MESSAGE_DELIVERED."""
        cookie = message.payload["cookie"]
        self.log.debug(f"Received ACK for message with cookie {cookie}")
        await self.downstream_system_message_queue.put(message)

    async def __handle_message_nack_message_not_delivered(
        self, message: CansMessage
    ) -> None:
        """Handle message type NACK_MESSAGE_NOT_DELIVERED."""
        peer = message.payload["message_target"]

        # TODO-UI implement behaviour of peer unavailable
        self.log.warning(f"Peer {peer} unavailable!")
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
        pending_messages = self.session_sm.flush_pending_session(peer)
        # Mark session as active
        self.session_sm.mark_outbound_session_active(message)

        # Send the pending messages
        for message in pending_messages:
            await self.send_message(message)

    def _encrypt_message_payload(self, message: CansMessage) -> CansMessage:
        """Encrypt different parts of the payload depending on message ID."""
        receiver = message.header.receiver
        msg_id = message.header.msg_id

        if msg_id == CansMsgId.USER_MESSAGE:
            message.payload["text"] = self._encrypt_text(
                receiver, message.payload["text"]
            )
        elif msg_id == CansMsgId.PEER_HELLO:
            message.payload["magic"] = self._encrypt_text(
                receiver, message.payload["magic"]
            )
        elif msg_id == CansMsgId.SESSION_ESTABLISHED:
            message.payload["magic"] = self._encrypt_text(
                receiver, message.payload["magic"]
            )
        else:
            self.log.error(
                f"Attempted encryption of unsupported message: {msg_id}"
            )

        return message

    def _encrypt_text(self, receiver: str, payload: str) -> str:
        """Encrypt the payload of a user message."""
        encrypt = self.session_sm.get_encryption_callback(receiver)
        olm_message = encrypt(payload)
        return olm_message.ciphertext

    def _decrypt_text(self, sender: str, payload: str) -> str:
        """Decrypt the payload of a user message."""
        decrypt = self.session_sm.get_decryption_callback(sender)
        olm_message = OlmMessage(payload)
        return decrypt(olm_message)
