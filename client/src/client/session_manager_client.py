"""Clientside session manager."""

import asyncio
import logging
import ssl
from typing import Dict

import websockets.client as ws
from olm import Account, OlmMessage, OlmPreKeyMessage

from common.keys import PubKeyDigest
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
from .key_manager import KeyManager


class ActiveSession(DoubleRatchetSession):
    """Interface for SessionManager convenience."""

    pass


class PotentialSession:
    """Utility mapping friends pub_keys on (id_keys, ot_keys)."""

    def __init__(self, identity_key: str, one_time_key: str):
        """Construct easy way of finding public bundle."""
        self.identity_key = identity_key
        self.one_time_key = one_time_key

    def transform_to_active_session(self, account: Account) -> ActiveSession:
        """Hide logic of transforming potential session to active session."""
        identity_key, one_time_key = (
            self.identity_key,
            self.one_time_key,
        )
        active_session = ActiveSession(account=account)
        active_session.start_outbound_session(
            peer_id_key=identity_key, peer_one_time_key=one_time_key
        )
        return active_session


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
        self.active_sessions: Dict[PubKeyDigest, ActiveSession] = {}
        self.potential_sessions: Dict[PubKeyDigest, PotentialSession] = {}

        # TODO: Implement client-side logging
        self.log = logging.getLogger("cans-logger")

        # TODO: Remove after alpha presentation
        self.hardcoded_peer_key = hardcoded_peer

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
            hello = ServerHello(
                public_key=public_key,
                subscriptions=[self.hardcoded_peer_key],
                identity_key=identity_key,
                one_time_keys=one_time_keys,
            )

            await cans_send(hello, conn)

            # For sure this message is ActiveFriends.
            active_friends_message: ActiveFriends = await cans_recv(conn)

            for (
                pub_key_digest,
                public_key_bundle,
            ) in active_friends_message.payload["friends"].items():
                identity_key, one_time_key = public_key_bundle
                self.potential_sessions[pub_key_digest] = PotentialSession(
                    identity_key=identity_key, one_time_key=one_time_key
                )

            # TODO delete self._dummy_message_generator()
            await asyncio.gather(  # noqa FKA01
                self._dummy_message_generator(),
                self._handle_upstream(conn),
                self._handle_downstream(conn),
            )

    # TODO delete it
    async def _dummy_message_generator(self) -> None:
        while True:
            public_key = self.key_manager.get_own_public_key_digest()

            dummy_message = self._user_message_to(self.hardcoded_peer_key)
            plaintext = (
                f"Hello {self.hardcoded_peer_key}, this is {public_key}"
            )
            dummy_message.payload = plaintext

            await self.upstream_message_queue.put(dummy_message)
            await asyncio.sleep(2)

    async def _handle_upstream(self, conn: ws.WebSocketClientProtocol) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = await self.upstream_message_queue.get()
            receiver = message.header.receiver

            if receiver is not None:
                if receiver in self.potential_sessions.keys():
                    # remove entry from potential sessions
                    potential_session = self.potential_sessions.pop(receiver)
                    # transform potential session to active session
                    active_session = (
                        potential_session.transform_to_active_session(
                            account=self.account
                        )
                    )
                    self.active_sessions[receiver] = active_session

                if receiver in self.active_sessions.keys():
                    olm_message = self.active_sessions[receiver].encrypt(
                        message.payload
                    )
                    message.payload = olm_message.ciphertext

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
                + f" {message.header.sender} that decrypted to {plaintext}."
            )
        elif sender in self.active_sessions.keys():
            olm_message = OlmMessage(ciphertext)
            plaintext = self.active_sessions[sender].decrypt(olm_message)
            print(
                f"Received encrypted user message {ciphertext} from"
                + f" {message.header.sender} that decrypted to {plaintext}."
            )
        else:
            # TODO-UI implement behaviour of new user message
            print("User message from the other side of the moon.")

    async def _handle_message_peer_unavailable(
        self, message: CansMessage
    ) -> None:
        """Handle message type PEER_UNAVAILABLE."""
        peer = message.payload["peer"]

        # TODO-UI implement behaviour of peer unavailable
        print(f"Peer {peer} unavailable!")

    async def _handle_message_peer_login(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGIN."""
        peer = message.payload["peer"]
        identity_key, one_time_key = message.payload["public_keys_bundle"]
        self.potential_sessions[peer] = PotentialSession(
            identity_key=identity_key, one_time_key=one_time_key
        )

        # TODO-UI implement behaviour of user login
        print(f"Peer {peer} just logged in!")

    async def _handle_message_peer_logout(self, message: CansMessage) -> None:
        """Handle message type PEER_LOGOUT."""
        peer = message.payload["peer"]

        if peer in self.potential_sessions.keys():
            self.potential_sessions.pop(peer)
        elif peer in self.active_sessions.keys():
            self.active_sessions.pop(peer)

        # TODO-UI implement behaviour of user logout
        print(f"Peer {peer} just logged out!")

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

    def _user_message_to(self, peer: PubKeyDigest) -> UserMessage:
        """Create a user message to a peer."""
        message = UserMessage(peer)
        message.header.sender = self.key_manager.get_own_public_key_digest()
        return message
