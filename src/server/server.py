"""Dummy server application."""

import asyncio
import os
from datetime import datetime

import websockets.server as ws


class Server:
    """Dummy server class."""

    def __init__(self) -> None:
        """Initialize and start the cans server."""
        eventLoop = asyncio.get_event_loop()
        stopFuture = eventLoop.create_future()
        eventLoop.run_until_complete(self.ServerStart(stopFuture))

    async def ConnectionHandler(
        self, conn: ws.WebSocketServerProtocol
    ) -> None:
        """Handle a client connection."""
        print(f"Accepted a connection from {conn.remote_address}")
        await conn.send(str(datetime.now()))

    async def ServerStart(self, stopAwaitable: asyncio.Future) -> None:
        """Run a WebSockets server."""
        port = os.environ["CANS_PORT"]
        host = os.environ["CANS_SERVER_HOSTNAME"]

        async with ws.serve(
            ws_handler=self.ConnectionHandler,
            host=host,
            port=int(port),
        ):
            await stopAwaitable


if __name__ == "__main__":
    Server()
