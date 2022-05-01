"""Upstream traffic handler."""

import logging
from typing import Callable, Dict

from common.keys import PubKeyDigest
from common.messages import CansMessage, CansMsgId, cans_recv
from server.client_session import ClientSession


class SessionUpstreamHandler:
    """Upstream messages handler.

    Aggregates methods related to handling upstream traffic, i.e.
    from the client to the server.
    """

    def __init__(
        self,
        sessions: Dict[PubKeyDigest, ClientSession],
        cans_router: Callable,
    ) -> None:
        """Construct the upstream handler."""
        self.log = logging.getLogger("cans-logger")
        # Store a router callback if downstream routing is needed
        self.route_message = cans_router
        # Keep reference to the managed sessions
        self.sessions = sessions
        self.message_handlers = {
            CansMsgId.USER_MESSAGE: self.__handle_message_user_message,
            CansMsgId.SHARE_CONTACTS: self.__handle_message_share_contacts,
        }

    async def handle_upstream(self, session: ClientSession) -> None:
        """Handle upstream traffic, i.e. client to server.

        This API is exposed to the session manager so that it
        can dispatch upstream handling here.
        """
        while True:
            # Receive a message from the socket
            message = await cans_recv(session.connection)

            # Validate the message header
            if self.__upstream_message_valid(message, session):
                msg_id = message.header.msg_id
                if msg_id in self.message_handlers.keys():
                    # Call the relevant handler
                    await self.message_handlers[msg_id](message, session)
                else:
                    self.log.warning(f"Unsupported message ID: {msg_id}")
            else:
                # TODO: Should we terminate the connection here?
                self.log.warning(
                    "Received malformed message from"
                    + f" {session.public_key_digest}:"
                    + f" id={message.header.msg_id},"
                    + f" sender={message.header.sender},"
                    + f" receiver={message.header.receiver}"
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

    def __upstream_message_valid(
        self, message: CansMessage, session: ClientSession
    ) -> bool:
        """Validate an inbound message with regards to the current session."""
        return message.header.sender == session.public_key_digest
