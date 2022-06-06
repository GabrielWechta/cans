"""Upstream traffic handler."""

import logging
from typing import Callable, Dict

from common.connection import CansStatusCode
from common.messages import (
    CansMalformedMessageError,
    CansMessage,
    CansMessageException,
    CansMsgId,
    cans_recv,
)
from server.client_session import ClientSession
from server.database_manager_server import DatabaseManager
from server.session_event import LoginEvent, LogoutEvent, SessionEvent


class SessionUpstreamHandler:
    """Upstream messages handler.

    Aggregates methods related to handling upstream traffic, i.e.
    from the client to the server.
    """

    def __init__(
        self,
        sessions: Dict[str, ClientSession],
        route_message_callback: Callable,
        database_manager: DatabaseManager,
    ) -> None:
        """Construct the upstream handler."""
        self.log = logging.getLogger("cans-logger")
        # Store a reference to the managed sessions
        self.sessions = sessions
        # Store a callback for routing messages between handlers
        self.route_message = route_message_callback
        # Store a reference to the database manager
        self.database_manager = database_manager
        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self.__handle_message_user_message,
            CansMsgId.SHARE_CONTACTS: self.__handle_message_share_contacts,
            CansMsgId.PEER_HELLO: self.__handle_message_peer_hello,
            CansMsgId.ADD_FRIEND: self.__handle_message_add_friend,
            CansMsgId.REQUEST_LOGOUT_NOTIF: self.__handle_request_logout_notif,
            # fmt: off
            CansMsgId.SESSION_ESTABLISHED:
                self.__handle_message_session_established,
            CansMsgId.REPLENISH_ONE_TIME_KEYS_RESP:
                self.__handle_message_replenish_one_time_keys_req,
            # fmt: on
        }

    async def handle_upstream(self, session: ClientSession) -> None:
        """Handle upstream traffic, i.e. client to server.

        This API is exposed to the session manager so that it
        can dispatch upstream handling here.
        """
        try:
            while True:
                # Receive a message from the socket
                message = await cans_recv(session.connection)

                # Validate the message header
                self.__assert_valid_upstream_message(message, session)

                msg_id = message.header.msg_id
                if msg_id in self.message_handlers.keys():
                    # Call the relevant handler
                    await self.message_handlers[msg_id](message, session)
                else:
                    self.log.warning(f"Unsupported message ID: {msg_id}")

        except (CansMessageException, AttributeError, KeyError) as e:
            self.log.error(
                f"{type(e).__name__} in session"
                + f" with {session.hostname}:{session.port}: {str(e)}"
            )
            await session.connection.close(
                code=CansStatusCode.MALFORMED_MESSAGE,
                reason="Malformed message",
            )

    async def __handle_message_user_message(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type USER_MESSAGE."""
        # User traffic - just route it
        await self.route_message(message)

    async def __handle_message_share_contacts(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type SHARE_CONTACTS."""
        # User traffic - just route it
        await self.route_message(message)

    async def __handle_message_peer_hello(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type PEER_HELLO."""
        # User traffic - just route it
        await self.route_message(message)

    async def __handle_message_add_friend(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type ADD_FRIEND."""
        peer = message.payload["friend"]
        self.log.debug(f"User {session.user_id} added friend {peer}")
        session.subscriptions.add(peer)
        await self.database_manager.add_subscriber_of(peer, session.user_id)
        # Check if the new friend is online
        if peer in self.sessions.keys():
            # Peer online, send login event
            event = LoginEvent(peer)
            await self.__send_event(event, session)

    async def __handle_request_logout_notif(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type REQUEST_LOGOUT_NOTIF."""
        peer = message.payload["peer"]

        self.log.debug(
            f"User '{session.user_id}' requested logout notification"
            + f" for peer '{peer}'"
        )
        if peer in self.sessions.keys():
            # Peer is still active, add us to their one-time subscribers set
            self.sessions[peer].one_time_subscribers.add(session.user_id)
        else:
            # Peer is offline, send logout notification immediately to
            # remediate the race condition
            self.log.info(
                f"'{peer}' already offline when '{session.user_id}'"
                + " requested logout notification"
            )
            event = LogoutEvent(peer)
            await self.__send_event(event, session)

    async def __handle_message_session_established(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type SESSION_ESTABLISHED."""
        # User traffic - just route it
        await self.route_message(message)

    async def __handle_message_replenish_one_time_keys_req(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type REPLENISH_ONE_TIME_KEYS_REQ."""
        keys = message.payload["keys"]
        self.log.debug(
            f"User '{session.user_id}' replenished"
            + f" {len(keys)} one-time keys"
        )
        # TODO: Is any validation of the keys needed? This is authenticated
        # user and the keys are not used by the server, so likely not...
        session.add_one_time_keys(keys)

    def __assert_valid_upstream_message(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Validate an inbound message with regards to the current session."""
        if message.header.sender != session.user_id:
            raise CansMalformedMessageError(
                f"Header field 'sender' invalid: {message.header.sender}"
            )

    async def __send_event(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Send an event.

        The event shall be handled in the relevant session's
        downstream handler.
        """
        await session.event_queue.put(event)
