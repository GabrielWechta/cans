"""Peer sessions state machine.

There are three types of sessions we consider in CANS:
a Potential Session, a Pending Session and an Active
Session.

A Potential Session is only a utility mapping between
peer's public keys (used for identification) and their
identity and one-time keys (used for end-to-end encryption).
A Potential Session transitions into a Pending Session
when an outbound user message is pushed from the user
interface to the session manager:

                  outbound user message
POTENTIAL SESSION ---------------------> PENDING SESSION

A Pending Session is a session started by the local client,
but not yet acknowledged by the remote peer. A pre-key message
is sent to the peer and we wait for the ACK. Upon receiving it
a Pending Session becomes an Active Session:

                session established ack
PENDING SESSION -----------------------> ACTIVE_SESSION

An Active Session has a well-established session key known to
both communicating parties. A Potential Session may transition
directly to an Active Session when a pre-key message from the
relevant peer is received:

                  inbound pre-key message
POTENTIAL_SESSION -----------------------> ACTIVE_SESSION
"""

import logging
from typing import Callable, Dict, List

from olm import Account, OlmMessage, OlmPreKeyMessage

from common.keys import PubKeyDigest
from common.messages import CANS_PEER_HANDSHAKE_MAGIC, CansMessage

from .e2e_encryption import DoubleRatchetSession


class StateMachineInconsistency(Exception):
    """Internal error."""

    ...


class ActiveSession(DoubleRatchetSession):
    """A well-established session."""

    ...


class PotentialSession:
    """A map between peer's public key and crypto context."""

    def __init__(self, identity_key: str, one_time_key: str) -> None:
        """Initialize a potential session."""
        self.identity_key = identity_key
        self.one_time_key = one_time_key


class PendingSession:
    """A requested, but not yet acknowledged session."""

    def __init__(
        self, account: Account, identity_key: str, one_time_key: str
    ) -> None:
        """Initialize a pending session."""
        self.active_session = ActiveSession(account)
        self.identity_key = identity_key
        self.one_time_key = one_time_key
        self.buffered_messages: List[CansMessage] = []
        # Initialize the olm interface to encrypt the user payload
        self.active_session.start_outbound_session(
            self.identity_key, self.one_time_key
        )

    def buffer_message(self, message: CansMessage) -> None:
        """Buffer a user message."""
        self.buffered_messages.append(message)


class SessionsStateMachine:
    """Peer sessions state machine."""

    def __init__(self, account: Account) -> None:
        """Instantiate the state machine."""
        self.account = account
        self.log = logging.getLogger("cans-logger")
        self.active_sessions: Dict[PubKeyDigest, ActiveSession] = {}
        self.pending_sessions: Dict[PubKeyDigest, PendingSession] = {}
        self.potential_sessions: Dict[PubKeyDigest, PotentialSession] = {}

    def get_active_session(self, peer: PubKeyDigest) -> ActiveSession:
        """Fetch an active session."""
        assert (
            peer in self.active_sessions.keys()
        ), "Sessions state machine inconsistency"
        return self.active_sessions[peer]

    def get_encryption_callback(self, peer: PubKeyDigest) -> Callable:
        """Fetch an encryption callback associated with a session."""
        if peer in self.active_sessions.keys():
            return self.active_sessions[peer].encrypt
        elif peer in self.pending_sessions.keys():
            return self.pending_sessions[peer].active_session.encrypt
        else:
            raise StateMachineInconsistency(
                "Tried fetching an encryption callback for an"
                + f" invalid session with peer {peer}"
            )

    def get_decryption_callback(self, peer: PubKeyDigest) -> Callable:
        """Fetch a decryption callback associated with a session."""
        if peer in self.active_sessions.keys():
            return self.active_sessions[peer].decrypt
        elif peer in self.pending_sessions.keys():
            return self.pending_sessions[peer].active_session.decrypt
        else:
            raise StateMachineInconsistency(
                "Tried fetching a decryption callback for an"
                + f" invalid session with peer {peer}"
            )

    def add_potential_session(
        self, peer: PubKeyDigest, identity_key: str, one_time_key: str
    ) -> None:
        """Add a new potential session."""
        self.potential_sessions[peer] = PotentialSession(
            identity_key,
            one_time_key,
        )

    def terminate_session(self, peer: PubKeyDigest) -> None:
        """Terminate a session, no matter its type."""
        if peer in self.potential_sessions.keys():
            self.potential_sessions.pop(peer)
        elif peer in self.pending_sessions.keys():
            self.pending_sessions.pop(peer)
        elif peer in self.active_sessions.keys():
            self.active_sessions.pop(peer)

    def make_session_pending(
        self, peer: PubKeyDigest, user_message: CansMessage
    ) -> None:
        """Transition from Potential Session to Pending Session."""
        potential_session = self.potential_sessions.pop(peer)
        self.pending_sessions[peer] = PendingSession(
            account=self.account,
            identity_key=potential_session.identity_key,
            one_time_key=potential_session.one_time_key,
        )

        # Buffer the user message
        self.pending_sessions[peer].buffer_message(user_message)

    def pend_message(self, peer: PubKeyDigest, message: CansMessage) -> None:
        """Buffer a pending user message."""
        self.pending_sessions[peer].buffer_message(message)

    def flush_pending_session(self, peer: PubKeyDigest) -> List[CansMessage]:
        """Flush messages buffered while waiting for session ACK."""
        backlog = self.pending_sessions[peer].buffered_messages
        self.pending_sessions[peer].buffered_messages = []
        return backlog

    def mark_outbound_session_active(self, message: CansMessage) -> None:
        """Transition from Pending Session to Active Session."""
        peer = message.header.sender
        self.log.debug(f"Activating outbound session with peer {peer}...")
        pending_session = self.pending_sessions.pop(peer)
        # Recover the active session from the pending session
        self.active_sessions[peer] = pending_session.active_session
        # Run decryption to have the session well established at
        # olm level - without this, olm will continue producing
        # prekey messages
        olm_message = OlmMessage(message.payload)
        assert (
            self.active_sessions[peer].decrypt(olm_message)
            == CANS_PEER_HANDSHAKE_MAGIC
        ), "Magic valu in peer handshake invalid"

    def activate_inbound_session(self, message: CansMessage) -> None:
        """Activate an inbound session based on a received prekey message."""
        peer = message.header.sender
        self.log.debug(f"Activating inbound session with {peer}...")
        prekey_message = OlmPreKeyMessage(message.payload)
        # Remove peer from potential/pending sessions if present
        if peer in self.potential_sessions:
            self.potential_sessions.pop(peer)
        if peer in self.pending_sessions:
            self.pending_sessions.pop(peer)
        # Activate a new session
        active_session = ActiveSession(account=self.account)
        active_session.start_inbound_session(prekey_message)
        # Store new active session
        self.active_sessions[peer] = active_session
        assert (
            active_session.decrypt(prekey_message) == CANS_PEER_HANDSHAKE_MAGIC
        ), "Magic value in peer handshake invalid"
