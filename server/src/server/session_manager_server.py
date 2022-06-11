"""Serverside session manager."""

import asyncio
import logging
from typing import Callable, Dict, Set

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from common.keys import PublicKeysBundle
from common.messages import (
    ActiveFriends,
    CansMessage,
    NackMessageNotDelivered,
    cans_send,
)
from server.session_downstream_handler import SessionDownstreamHandler
from server.session_upstream_handler import SessionUpstreamHandler

from .client_session import ClientSession
from .database_manager_server import DatabaseManager
from .session_event import (
    LoginEvent,
    LogoutEvent,
    MessageEvent,
    ReplenishKeysEvent,
)


class SessionManager:
    """Client session manager.

    Manage client sessions and maintain a mapping between
    client's public keys and event queues corresponding
    to their sessions.
    """

    MAX_ONE_TIME_KEYS = 10
    ONE_TIME_KEYS_REPLENISH_THRESHOLD = MAX_ONE_TIME_KEYS // 2

    def __init__(self) -> None:
        """Construct a session manager instance."""
        # Get the logger
        self.log = logging.getLogger("cans-logger")
        # Map public keys to ClientSessions
        self.sessions: Dict[str, ClientSession] = {}
        # Start DatabaseManager
        self.database_manager = DatabaseManager()

        # Instantiate the traffic handlers
        self.downstream_handler = SessionDownstreamHandler(
            self.sessions, self.__get_key_bundle
        )
        self.upstream_handler = SessionUpstreamHandler(
            sessions=self.sessions,
            route_message_callback=self.__route_message,
            get_key_bundle_callback=self.__get_key_bundle,
            database_manager=self.database_manager,
        )

    async def authed_user_entry(
        self,
        conn: WebSocketServerProtocol,
        user_id: str,
        subscriptions: Set[str],
        identity_key: str,
        one_time_keys: Dict[str, str],
    ) -> None:
        """Handle an authenticated user."""
        # Save the session to have consistent state when
        # sending notifications and talking to the client
        session = ClientSession(
            conn=conn,
            user_id=user_id,
            subscriptions=subscriptions,
            identity_key=identity_key,
            one_time_keys=one_time_keys,
        )
        self.sessions[user_id] = session

        # Update subscriptions data in the database
        await self.__update_subscriptions_database(user_id, subscriptions)
        # Send login events to all subscribers
        await self.__notify_subscribers(user_id, LoginEvent)
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
            await self.__handle_connection_closed(user_id, e)

    async def __route_message(self, message: CansMessage) -> None:
        """Route the message to the receiver."""
        sender = message.header.sender
        receiver = message.header.receiver
        self.log.debug(f"Routing message from '{sender}' to '{receiver}'")

        if receiver in self.sessions.keys():
            # Wrap the message in an event and
            # send it to the appropriate receiver
            event = MessageEvent(message)
            await self.downstream_handler.send_event(event, receiver)
        elif sender:
            # Do not reroute server messages so as to not get
            # into an infinite recursion
            notification = NackMessageNotDelivered(
                receiver=sender,
                message_target=receiver,
                message_id=message.header.msg_id,
                # Note that cookie may not be present as no payload validation
                # is done serverside and the message need not be USER_MESSAGE,
                # but may also be, e.g. PEER_HELLO
                extra=message.payload["cookie"]
                if "cookie" in message.payload.keys()
                else "",
                reason="Peer unavailable",
            )
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

    async def __get_key_bundle(self, client: str) -> PublicKeysBundle:
        """Fetch peer's public keys bundle."""
        session = self.sessions[client]
        # TODO: Properly handle a race condition when no keys are available
        one_time_key = session.pop_one_time_key()

        self.log.debug(f"Popping one-time key of user '{session.user_id}'...")

        if session.remaining_keys() < self.ONE_TIME_KEYS_REPLENISH_THRESHOLD:
            self.log.debug(
                "Requesting a replenishment of keys of user"
                + f" '{session.user_id}'..."
            )
            # If too few keys remaining on the server, request a replenishment
            event = ReplenishKeysEvent(
                self.MAX_ONE_TIME_KEYS - session.remaining_keys()
            )
            await self.downstream_handler.send_event(event, client)

        return session.identity_key, one_time_key

    async def __handle_active_friends_notification(
        self, session: ClientSession
    ) -> None:
        """Find active friends of the new client and send a notification."""
        # Check for active users in the subscription list
        active_friends: Dict[str, PublicKeysBundle] = {}
        for friend in session.subscriptions:
            if friend in self.sessions.keys():
                active_friends[friend] = await self.__get_key_bundle(friend)

        active_friends_notification = ActiveFriends(
            session.user_id, active_friends
        )
        await cans_send(active_friends_notification, session.connection)

    async def __notify_subscribers(
        self, user_id: str, event_constructor: Callable
    ) -> None:
        """Notify all subscribers about successful login."""
        subscribers = await self.database_manager.get_subscribers_of(user_id)

        # Notify all subscribers
        for sub in subscribers:
            if sub in self.sessions.keys():
                # Send an event to all interested parties
                event = event_constructor(user_id)
                await self.downstream_handler.send_event(event, sub)

    async def __update_subscriptions_database(
        self,
        user_id: str,
        subscriptions: Set[str],
    ) -> None:
        # Add subscriptions to the database
        for peer in subscriptions:
            self.log.debug(f"User '{user_id}' subscribing for '{peer}'")
            await self.database_manager.add_subscriber_of(peer, user_id)

    async def __handle_connection_closed(
        self, user_id: str, exception: ConnectionClosed
    ) -> None:
        """Handle the client closing the connection."""
        # Remove the client's session
        session = self.sessions.pop(user_id)
        self.log.info(
            f"Connection with {session.hostname}:{session.port}"
            + f" closed with code {exception.code}"
        )

        # Notify all subscribers
        await self.__notify_subscribers(user_id, LogoutEvent)
        # Send out one-time logout notifications
        await self.__handle_one_time_logout_notifs(
            user_id, session.one_time_subscribers
        )

    async def __handle_one_time_logout_notifs(
        self, user_id: str, subscribers: Set[str]
    ) -> None:
        """Send out one-time logout notifications."""
        count = 0

        for sub in subscribers:
            if sub in self.sessions.keys():
                # Send a logout event to all interested parties
                event = LogoutEvent(user_id)
                await self.downstream_handler.send_event(event, sub)
                count += 1

        self.log.debug(f"Sent one-time logout notification to {count} users")
