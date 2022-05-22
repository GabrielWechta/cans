"""Downstream traffic handler."""

import logging
from typing import Any, Callable, Dict

from common.messages import (
    AckMessageDelivered,
    CansMessage,
    CansMsgId,
    PeerLogin,
    PeerLogout,
    ReplenishOneTimeKeysReq,
    cans_send,
)
from server.client_session import ClientSession

from .session_event import EventType, MessageEvent, SessionEvent


class SessionDownstreamHandler:
    """Downstream events handler.

    Aggregates methods related to handling downstream traffic, i.e.
    from the server to the client.
    """

    def __init__(
        self,
        sessions: Dict[str, ClientSession],
        get_one_time_key_callback: Callable,
    ) -> None:
        """Construct the downstream handler."""
        self.log = logging.getLogger("cans-logger")
        # Store a reference to the managed sessions
        self.sessions = sessions
        # Store a reference to the parent session manager
        self.get_one_time_key = get_one_time_key_callback
        # Set up event handlers
        self.event_handlers = {
            EventType.MESSAGE: self.__handle_event_message,
            EventType.LOGIN: self.__handle_event_login,
            EventType.LOGOUT: self.__handle_event_logout,
            EventType.REPLENISH_KEYS: self.__handle_event_replenish_keys,
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

    async def send_event(self, event: SessionEvent, client: str) -> None:
        """Send an event.

        The event shall be handled in the relevant session's
        downstream handler.
        """
        session = self.sessions[client]
        await session.event_queue.put(event)

    async def __handle_event_message(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type MESSAGE."""
        message: CansMessage = event.payload

        # Forward the user message downstream to the client
        await cans_send(message, session.connection)

        # Acknowledge user messages
        if message.header.msg_id == CansMsgId.USER_MESSAGE:
            await self.__ack_user_message(message)

    async def __ack_user_message(self, message: CansMessage) -> None:
        """Send delivery acknowledgement back to sender."""
        sender = message.header.sender

        ack_message = AckMessageDelivered(
            receiver=sender,
            message_target=message.header.receiver,
            cookie=message.payload["cookie"],
        )

        event = MessageEvent(ack_message)
        await self.send_event(event, sender)

    async def __handle_event_login(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type LOGIN."""
        assert isinstance(event.payload, dict)
        payload: Dict[str, Any] = event.payload
        peer = payload["peer"]
        peer_key_bundle = (
            self.sessions[peer].identity_key,
            await self.get_one_time_key(peer),
        )
        # Wrap the event in a CANS message and send downstream to the client
        message = PeerLogin(
            receiver=session.user_id,
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
        message = PeerLogout(session.user_id, payload["peer"])
        await cans_send(message, session.connection)

    async def __handle_event_replenish_keys(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Handle session event of type REPLENISH_KEYS."""
        assert isinstance(event.payload, dict)
        payload: Dict[str, Any] = event.payload
        # Wrap the event in a CANS message and send downstream to the client
        message = ReplenishOneTimeKeysReq(session.user_id, payload["count"])
        await cans_send(message, session.connection)

    async def __get_event(self, session: ClientSession) -> SessionEvent:
        """Receive an event from the session's event queue."""
        return await session.event_queue.get()