"""Downstream traffic handler."""

import logging
from typing import Any, Dict

from common.keys import PubKeyDigest
from common.messages import CansMessage, PeerLogin, PeerLogout, cans_send
from server.client_session import ClientSession

from .session_event import EventType, SessionEvent


class SessionDownstreamHandler:
    """Downstream events handler.

    Aggregates methods related to handling downstream traffic, i.e.
    from the server to the client.
    """

    def __init__(self, sessions: Dict[PubKeyDigest, ClientSession]) -> None:
        """Construct the downstream handler."""
        self.log = logging.getLogger("cans-logger")
        # Keep reference to the managed sessions
        self.sessions = sessions
        # Set up event handlers
        self.event_handlers = {
            EventType.MESSAGE: self.__handle_event_message,
            EventType.LOGIN: self.__handle_event_login,
            EventType.LOGOUT: self.__handle_event_logout,
        }

    async def handle_downstream(self, session: ClientSession) -> None:
        """Handle downstream traffic, i.e. server to client.

        This API is exposed to the session manager so that it
        can dispatch downstream handling here.
        """
        while True:
            event: SessionEvent = await self.__get_event(session)
            if event.event_type in self.event_handlers.keys():
                # Call a registered event handler
                await self.event_handlers[event.event_type](event, session)
            else:
                self.log.warning(f"Unsupported event type: {event.event_type}")

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
            self.sessions[peer].pop_one_time_key(),
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

    async def __get_event(self, session: ClientSession) -> SessionEvent:
        """Receive an event from the session's event queue."""
        return await session.event_queue.get()
