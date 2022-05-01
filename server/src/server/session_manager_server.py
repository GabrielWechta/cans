"""Serverside session manager."""

import asyncio
import logging
from typing import Any, Dict, List

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from common.keys import PubKeyDigest, PublicKeysBundle
from common.messages import (
    ActiveFriends,
    CansMessage,
    CansMsgId,
    PeerLogin,
    PeerLogout,
    PeerUnavailable,
    ReplenishOneTimeKeysReq,
    cans_recv,
    cans_send,
)

from .client_session import ClientSession
from .database_manager_server import DatabaseManager
from .session_event import (
    EventType,
    LoginEvent,
    LogoutEvent,
    MessageEvent,
    ReplenishKeysEvent,
    SessionEvent,
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
        self.sessions: Dict[str, ClientSession] = dict()
        # Start DatabaseManager
        self.database_manager = DatabaseManager()
        # Set up event handlers
        self.event_handlers = {
            EventType.MESSAGE: self.__handle_event_message,
            EventType.LOGIN: self.__handle_event_login,
            EventType.LOGOUT: self.__handle_event_logout,
            EventType.REPLENISH_KEYS: self.__handle_event_replenish_keys,
        }

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

        # Add subscriptions to the database
        for peer in subscriptions:
            self.log.debug(
                f"User '{public_key_digest}' subscribing for {peer}"
            )
            await self.database_manager.add_subscriber_of(
                peer, public_key_digest
            )

        # Send login events to all subscribers
        await self.__handle_auth_success(public_key_digest)

        # Check for active users in the subscription list
        active_friends: Dict[PubKeyDigest, PublicKeysBundle] = {}
        for friend in subscriptions:
            if friend in self.sessions.keys():
                peer_session = self.sessions[friend]
                active_friends[friend] = (
                    peer_session.identity_key,
                    await self.__rotate_one_time_keys(peer_session),
                )

        active_friends_notification = ActiveFriends(
            public_key_digest, active_friends
        )
        await cans_send(active_friends_notification, conn)

        remote_host = conn.remote_address[0]
        remote_port = conn.remote_address[1]

        try:
            # Use fork-join semantics to run both upstream and
            # downstream handlers concurrently and wait for both
            # to terminate
            await asyncio.gather(
                self.__handle_upstream(session),
                self.__handle_downstream(session),
            )
        except ConnectionClosed as e:
            self.log.info(
                f"Connection with {remote_host}:{remote_port}"
                + f" closed with code {e.code}"
            )
            # Send logout events to all subscribers
            await self.__handle_connection_closed(public_key_digest)
            # Clean up the sessions dictionary
            del self.sessions[public_key_digest]

    async def __handle_auth_success(
        self, public_key_digest: PubKeyDigest
    ) -> None:
        """Notify all subscribers about successful login."""
        subscribers = await self.database_manager.get_subscribers_of(
            public_key_digest
        )

        # Notify all subscribers
        for sub in subscribers:
            if sub in self.sessions.keys():
                event = LoginEvent(public_key_digest)
                await self.__send_event(event, self.sessions[sub])

        self.log.debug(f"Sent login notification to {len(subscribers)} users")

    def __upstream_message_valid(
        self, message: CansMessage, session: ClientSession
    ) -> bool:
        """Validate an inbound message with regards to the current session."""
        return message.header.sender == session.public_key_digest

    async def __handle_upstream(self, session: ClientSession) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = await cans_recv(session.connection)

            if self.__upstream_message_valid(message, session):
                sender = message.header.sender
                receiver = message.header.receiver
                msg_id = message.header.msg_id
                self.log.debug(
                    f"Handling upstream message {msg_id} from"
                    + f" {sender} to {receiver}"
                )

                if self.__is_user_message(message):
                    await self.__route_message(message)
                else:
                    await self.__handle_control_message(message, session)
            else:
                # TODO: Should we terminate the connection here?
                self.log.warning(
                    "Received malformed message from"
                    + f" {session.public_key_digest}:"
                    + f" id={message.header.msg_id},"
                    + f" sender={message.header.sender},"
                    + f" receiver={message.header.receiver}"
                )

    async def __handle_control_message(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle a control message from the user."""
        if message.header.msg_id == CansMsgId.REPLENISH_ONE_TIME_KEYS_RESP:
            # Handle one-time key replenishment response
            keys = message.payload["keys"]
            self.log.debug(
                f"User '{session.public_key_digest}' replenished"
                + f" {len(keys)} one-time keys"
            )
            # TODO: Is any validation of the keys needed? This is authenticated
            # user and the keys are not used by the server, so likely not...
            session.add_one_time_keys(keys)
        else:
            self.log.error(
                "Received unsupported control message:"
                + f" {message.header.msg_id}"
            )

    async def __handle_downstream(self, session: ClientSession) -> None:
        """Handle downstream traffic, i.e. server to client."""
        while True:
            event: SessionEvent = await self.__get_event(session)
            if event.event_type in self.event_handlers.keys():
                # Call a registered event handler
                await self.event_handlers[event.event_type](event, session)
            else:
                self.log.error(f"Unsupported event type: {event.event_type}")

    def __is_user_message(self, message: CansMessage) -> bool:
        """Check if a user message."""
        # TODO: Also check here if "share contact" message or other
        # peer-to-peer C-plane traffic
        return message.header.msg_id == CansMsgId.USER_MESSAGE

    async def __route_message(self, message: CansMessage) -> None:
        """Route the message to the receiver."""
        self.log.debug(
            f"Routing message from '{message.header.sender}'"
            + f" to '{message.header.receiver}'"
        )

        if message.header.receiver in self.sessions.keys():
            # Wrap the message in an event and
            # send it to the appropriate receiver
            self.log.debug(
                f"Receiver '{message.header.receiver}' online."
                + " Sending event..."
            )
            event = MessageEvent(message)
            await self.__send_event(
                event, self.sessions[message.header.receiver]
            )
        elif message.header.sender:
            # Do not reroute server messages so as to not get
            # into an infinite recursion
            notification = PeerUnavailable(
                receiver=message.header.sender, peer=message.header.receiver
            )
            self.log.debug(
                f"Receiver '{message.header.receiver}' not available."
                + " Sending notification back to"
                + f" '{message.header.sender}'..."
            )
            await self.__route_message(notification)
        else:
            # Drop orphaned server message
            self.log.warning(
                f"Failed to route server message to {message.header.receiver}"
            )

    async def __handle_connection_closed(
        self, public_key_digest: PubKeyDigest
    ) -> None:
        """Notify all subscribers about connection closed."""
        subscribers = await self.database_manager.get_subscribers_of(
            public_key_digest
        )

        # Notify all subscribers
        for sub in subscribers:
            if sub in self.sessions.keys():
                event = LogoutEvent(public_key_digest)
                await self.__send_event(event, self.sessions[sub])

        self.log.debug(f"Sent logout notification to {len(subscribers)} users")

    async def __handle_event_message(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type MESSAGE."""
        message: CansMessage = event.payload
        self.log.debug(
            f"Received message '{message.payload}' from"
            + f" '{message.header.sender}'"
        )
        # Forward the user message downstream to the client
        await cans_send(message, session.connection)

    async def __handle_event_login(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type LOGIN."""
        assert isinstance(event.payload, dict)
        payload: Dict[str, Any] = event.payload
        peer = payload["peer"]
        peer_key_bundle = (
            self.sessions[peer].identity_key,
            await self.__rotate_one_time_keys(self.sessions[peer]),
        )
        # Wrap the event in a CANS message and send downstream to the client
        message = PeerLogin(
            receiver=session.public_key_digest,
            peer=peer,
            public_keys_bundle=peer_key_bundle,
        )
        await cans_send(message, session.connection)

    async def __handle_event_logout(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type LOGOUT."""
        assert isinstance(event.payload, dict)
        payload: Dict[str, Any] = event.payload
        # Wrap the event in a CANS message and send downstream to the client
        message = PeerLogout(session.public_key_digest, payload["peer"])
        await cans_send(message, session.connection)

    async def __handle_event_replenish_keys(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type REPLENISH_KEYS."""
        assert isinstance(event.payload, dict)
        payload: Dict[str, Any] = event.payload
        # Wrap the event in a CANS message and send downstream to the client
        message = ReplenishOneTimeKeysReq(
            session.public_key_digest, payload["count"]
        )
        await cans_send(message, session.connection)

    async def __send_event(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Send an event."""
        await session.event_queue.put(event)

    async def __get_event(self, session: ClientSession) -> SessionEvent:
        """Receive an event."""
        return await session.event_queue.get()

    async def __rotate_one_time_keys(self, session: ClientSession) -> str:
        """Pop peer's one-time key and request replenishment."""
        # TODO: Properly handle a race condition when no keys are available
        key = session.pop_one_time_key()

        self.log.debug(
            f"Popping one-time key of user '{session.public_key_digest}'..."
        )

        if session.remaining_keys() < self.ONE_TIME_KEYS_REPLENISH_THRESHOLD:
            self.log.debug(
                "Requesting a replenishment of keys of user"
                + f"'{session.public_key_digest}'..."
            )
            # If too few keys remaining on the server, request a replenishment
            event = ReplenishKeysEvent(
                self.MAX_ONE_TIME_KEYS - session.remaining_keys()
            )
            await self.__send_event(event, session)
        return key
