"""Client session manager."""

import asyncio
import json
from typing import Dict

import websockets.server as ws
from ClientSession import ClientSession


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

        # TODO: Prepare data structures for mapping keys to event queues
        # TODO: Start DatabaseManager
        pass

    async def authed_user_entry(
        self, conn: ws.WebSocketServerProtocol, public_key: str
    ) -> None:  # TODO: Fix the publicKey's type
        """Handle an authenticated user."""
        # Suppose Alice has just been authenticated
        # Alice sends her subscriber list to the server

        # TODO: Send subscription event EVENT_LOGIN(Alice) to each user who
        # subscribes for Alice events (fetch subscribers[Alice] from the DB)

        session = ClientSession(conn, public_key)

        # NOTE: For PoC purposes use a simple dictionary
        self.sessions[public_key] = session

        # Use fork-join semantics to run both upstream and downstream handlers
        # concurrently and wait for both to terminate
        await asyncio.gather(
            self.__handle_upstream(session), self.__handle_downstream(session)
        )

    async def __handle_upstream(self, session: ClientSession) -> None:
        """Handle upstream traffic, i.e. client to server."""
        while True:
            message = json.JSONDecoder().decode(
                str(await session.connection.recv())
            )
            sender = message["sender"]
            receiver = message["receiver"]

            print(f"Handling upstream message from {sender} to {receiver}")

            await self.__route_message(message)

    async def __handle_downstream(self, session: ClientSession) -> None:
        """Handle downstream traffic, i.e. server to client."""
        while True:
            event = await session.event_queue.get()

            sender = event["sender"]
            payload = event["payload"]

            print(f"Received message '{payload}' from {sender}")

            # Send the message downstream to the client
            await session.connection.send(json.JSONEncoder().encode(event))

    async def __route_message(
        self, message: dict
    ) -> None:  # TODO: Use custom type for the message
        """Route the message to the receiver."""
        receiver = message["receiver"]

        if receiver in self.sessions.keys():

            await self.sessions[receiver].event_queue.put(message)

        elif message["sender"] != "server":
            # Do not reroute server messages so as to not get
            # into an infinite recursion
            resp = {
                "sender": "server",
                "receiver": message["sender"],
                "payload": f"Peer {receiver} unavailable!",
            }
            await self.__route_message(resp)
