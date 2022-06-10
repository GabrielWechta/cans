"""Upstream traffic handler."""

import logging
from typing import Callable, Dict

from common.connection import CansStatusCode
from common.messages import (
    CansMalformedMessageError,
    CansMessage,
    CansMessageException,
    CansMsgId,
    GetOneTimeKeyResp,
    cans_recv,
)
from server.client_session import ClientSession
from server.database_manager_server import DatabaseManager
from server.session_event import (
    LoginEvent,
    LogoutEvent,
    MessageEvent,
    SessionEvent,
)


class SessionUpstreamHandler:
    """Upstream messages handler.

    Aggregates methods related to handling upstream traffic, i.e.
    from the client to the server.
    """

    def __init__(
        self,
        sessions: Dict[str, ClientSession],
        route_message_callback: Callable,
        get_key_bundle_callback: Callable,
        database_manager: DatabaseManager,
    ) -> None:
        """Construct the upstream handler."""
        self.log = logging.getLogger("cans-logger")
        # Store a reference to the managed sessions
        self.sessions = sessions
        # Store a callback for routing messages between handlers
        self.route_message = route_message_callback
        # Store a callback for fetching peers' public keys bundles
        self.get_key_bundle = get_key_bundle_callback
        # Store a reference to the database manager
        self.database_manager = database_manager
        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self.__handle_message_user_message,
            CansMsgId.SHARE_CONTACTS: self.__handle_message_share_contacts,
            CansMsgId.PEER_HELLO: self.__handle_message_peer_hello,
            CansMsgId.ADD_FRIEND: self.__handle_message_add_friend,
            # fmt: off
            CansMsgId.ACK_MESSAGE_DELIVERED:
                self.__handle_message_ack_message_delivered,
            CansMsgId.NACK_MESSAGE_NOT_DELIVERED:
                self.__handle_message_nack_message_not_delivered,
            CansMsgId.REQUEST_LOGOUT_NOTIF:
                self.__handle_message_request_logout_notif,
            CansMsgId.SESSION_ESTABLISHED:
                self.__handle_message_session_established,
            CansMsgId.REPLENISH_ONE_TIME_KEYS_RESP:
                self.__handle_message_replenish_one_time_keys_resp,
            CansMsgId.GET_ONE_TIME_KEY_REQ:
                self.__handle_message_get_one_time_key_req,
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

    async def __handle_message_ack_message_delivered(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type ACK_MESSAGE_DELIVERED."""
        # User traffic - just route it
        await self.route_message(message)

    async def __handle_message_nack_message_not_delivered(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type NACK_MESSAGE_NOT_DELIVERED."""
        # User traffic - route it provided the payload is not malicious
        sender = message.header.sender
        message_target = message.payload["message_target"]
        if message_target != sender:
            raise CansMalformedMessageError(
                f"NACK spoofing attempt: sender is '{sender}',"
                + f" NACKed message target is '{message_target}'"
            )
        await self.route_message(message)

    async def __handle_message_request_logout_notif(
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

    async def __handle_message_replenish_one_time_keys_resp(
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

    async def __handle_message_get_one_time_key_req(
        self, message: CansMessage, session: ClientSession
    ) -> None:
        """Handle message type GET_ONE_TIME_KEY_REQ."""
        peer = message.payload["peer"]

        if peer in self.sessions.keys():
            # If peer is offline do not send the response at all, the user
            # must have already received PEER_LOGOUT.
            response = GetOneTimeKeyResp(
                receiver=message.header.sender,
                peer=peer,
                public_keys_bundle=await self.get_key_bundle(peer),
            )
            # Skip the routing, send the message directly
            event = MessageEvent(response)
            await self.__send_event(event, session)

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
