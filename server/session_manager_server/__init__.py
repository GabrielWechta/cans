"""Serverside session manager."""

import asyncio
import logging
from typing import Dict

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from common.keys import PubKeyDigest
from common.messages import CansMessage, PeerUnavailable, cans_recv, cans_send

from .client_session import ClientSession
from .session_event import EventType, SessionEvent


class SessionManager:
    """Client session manager.

    Manage client sessions and maintain a mapping between
    client's public keys and event queues corresponding
    to their sessions.
    """

    def __init__(self) -> None:
        """Construct a session manager instance."""
        # Map public keys to ClientSessions
        self.sessions: Dict[str, ClientSession] = dict()
        # Get the logger
        self.log = logging.getLogger("cans-logger")

        # TODO: Prepare data structures for mapping keys to event queues
        # TODO: Start DatabaseManager
        pass

    async def authed_user_entry(
        self, conn: WebSocketServerProtocol, public_key_digest: PubKeyDigest
    ) -> None:
        """Handle an authenticated user."""
        # Suppose Alice has just been authenticated
        # Alice sends her subscriber list to the server

        # TODO: Send subscription event EVENT_LOGIN(Alice) to each user who
        # subscribes for Alice events (fetch subscribers[Alice] from the DB)

        session = ClientSession(conn, public_key_digest)

        # NOTE: For PoC purposes use a simple dictionary
        self.sessions[public_key_digest] = session

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
            # TODO: Clean up the sessions dictionary
            # TODO: Send LOGOUT events to subscribers

    async def __handle_upstream(self, session: ClientSession) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = await cans_recv(session.connection)
            sender = message.header.sender
            receiver = message.header.receiver

            self.log.debug(
                f"Handling upstream message from {sender} to {receiver}"
            )
            await self.__route_message(message)

    async def __handle_downstream(self, session: ClientSession) -> None:
        """Handle downstream traffic, i.e. server to client."""
        while True:
            event: SessionEvent = await self.__get_event(session)

            if event.event_type == EventType.MESSAGE:
                message: CansMessage = event.payload

                self.log.debug(
                    f"Received message '{message.payload}' from"
                    + f" '{message.header.sender}'"
                )

                # Send the message downstream to the client
                await cans_send(message, session.connection)
            else:
                self.log.debug(f"Unsupported event type: {event.event_type}")

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
            event = SessionEvent(payload=message)
            await self.__send_event(
                event, self.sessions[message.header.receiver]
            )
        elif message.header.sender != "":
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

    async def __send_event(
        self, event: SessionEvent, session: ClientSession
    ) -> None:
        """Send an event."""
        await session.event_queue.put(event)

    async def __get_event(self, session: ClientSession) -> SessionEvent:
        """Receive an event."""
        return await session.event_queue.get()
