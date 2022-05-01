"""Serverside session manager."""

import asyncio
import logging
from typing import Callable, Dict, List

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from common.keys import PubKeyDigest, PublicKeysBundle
from common.messages import (
    ActiveFriends,
    CansMessage,
    PeerUnavailable,
    cans_send,
)
from server.session_downstream_handler import SessionDownstreamHandler
from server.session_upstream_handler import SessionUpstreamHandler

from .client_session import ClientSession
from .database_manager_server import DatabaseManager
from .session_event import LoginEvent, LogoutEvent, MessageEvent, SessionEvent


class SessionManager:
    """Client session manager.

    Manage client sessions and maintain a mapping between
    client's public keys and event queues corresponding
    to their sessions.
    """

    def __init__(self) -> None:
        """Construct a session manager instance."""
        # Get the logger
        self.log = logging.getLogger("cans-logger")
        # Map public keys to ClientSessions
        self.sessions: Dict[PubKeyDigest, ClientSession] = {}
        # Start DatabaseManager
        self.database_manager = DatabaseManager()

        # Instantiate the traffic handlers
        self.downstream_handler = SessionDownstreamHandler(self.sessions)
        self.upstream_handler = SessionUpstreamHandler(
            self.sessions, self.__route_message
        )

    async def authed_user_entry(
        self,
        conn: WebSocketServerProtocol,
        public_key_digest: PubKeyDigest,
        subscriptions: List[PubKeyDigest],
        identity_key: str,
        one_time_keys: Dict[str, str],
    ) -> None:
        """Handle an authenticated user."""
        # Save the session to have consistent state when
        # sending notifications and talking to the client
        session = ClientSession(
            conn=conn,
            public_key_digest=public_key_digest,
            subscriptions=subscriptions,
            identity_key=identity_key,
            one_time_keys=one_time_keys,
        )
        self.sessions[public_key_digest] = session

        # Update subscriptions data in the database
        await self.__update_subscriptions_database(
            public_key_digest, subscriptions
        )
        # Send login events to all subscribers
        await self.__notify_subscribers(public_key_digest, LoginEvent)
        # Notify the client of their active friends
        await self.__handle_active_friends_notification(session)

        try:
            # Use fork-join semantics to run both upstream and
            # downstream handlers concurrently and wait for both
            # to terminate
            await asyncio.gather(
                self.upstream_handler.handle_upstream(session),
                self.downstream_handler.handle_downstream(session),
            )
        except ConnectionClosed as e:
            await self.__handle_connection_closed(public_key_digest, e)

    async def __handle_active_friends_notification(
        self, session: ClientSession
    ) -> None:
        """Find active friends of the new client and send a notification."""
        # Check for active users in the subscription list
        active_friends: Dict[PubKeyDigest, PublicKeysBundle] = {}
        for friend in session.subscriptions:
            if friend in self.sessions.keys():
                peer_session = self.sessions[friend]
                active_friends[friend] = (
                    peer_session.identity_key,
                    peer_session.pop_one_time_key(),
                )

        active_friends_notification = ActiveFriends(
            session.public_key_digest, active_friends
        )
        await cans_send(active_friends_notification, session.connection)

    async def __notify_subscribers(
        self, public_key_digest: PubKeyDigest, event_constructor: Callable
    ) -> None:
        """Notify all subscribers about successful login."""
        subscribers = await self.database_manager.get_subscribers_of(
            public_key_digest
        )

        # Notify all subscribers
        for sub in subscribers:
            if sub in self.sessions.keys():
                # Send a login event to all interested parties
                event = event_constructor(public_key_digest)
                await self.__send_event(event, self.sessions[sub])

        self.log.debug(f"Sent login notification to {len(subscribers)} users")

    async def __update_subscriptions_database(
        self,
        public_key_digest: PubKeyDigest,
        subscriptions: List[PubKeyDigest],
    ) -> None:
        # Add subscriptions to the database
        for peer in subscriptions:
            self.log.debug(
                f"User '{public_key_digest}' subscribing for {peer}"
            )
            await self.database_manager.add_subscriber_of(
                peer, public_key_digest
            )

    async def __route_message(self, message: CansMessage) -> None:
        """Route the message to the receiver."""
        sender = message.header.sender
        receiver = message.header.receiver
        self.log.debug(f"Routing message from '{sender}' to '{receiver}'")

        if receiver in self.sessions.keys():
            # Wrap the message in an event and
            # send it to the appropriate receiver
            self.log.debug(
                f"Receiver '{receiver}' online." + " Sending event..."
            )
            event = MessageEvent(message)
            await self.__send_event(event, self.sessions[receiver])
        elif sender:
            # Do not reroute server messages so as to not get
            # into an infinite recursion

            # TODO: Include a cookie or send back the user message
            # so that the client can try resending or otherwise
            # respond appropriately
            notification = PeerUnavailable(receiver=sender, peer=receiver)
            self.log.debug(
                f"Receiver '{receiver}' not available."
                + " Sending notification back to"
                + f" '{sender}'..."
            )
            await self.__route_message(notification)
        else:
            # Drop orphaned server message
            self.log.warning(
                f"Dropped server message {message.header.msg_id}"
                + f" destined to {message.header.receiver}"
            )

    async def __handle_connection_closed(
        self, public_key_digest: PubKeyDigest, exception: ConnectionClosed
    ) -> None:
        """Handle the client closing the connection."""
        # Remove the client's session
        session = self.sessions.pop(public_key_digest)
        self.log.info(
            f"Connection with {session.hostname}:{session.port}"
            + f" closed with code {exception.code}"
        )

        # Notify all subscribers
        await self.__notify_subscribers(public_key_digest, LogoutEvent)

    async def __send_event(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Send an event.

        The event shall be handled in the relevant session's
        downstream handler.
        """
        await session.event_queue.put(event)
