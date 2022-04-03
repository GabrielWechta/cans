"""Dummy server application."""

import asyncio
import os
import pathlib
import ssl
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

        sslContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        sslContext.load_cert_chain(
            # TODO: Resolve the certificate and key paths dynamically using
            # e.g. .env file (at least serverside, client uses the local
            # self-signed cert only for proof-of-concept purposes anyway)
            certfile=pathlib.Path(__file__).with_name("CansCert.pem"),
            keyfile=pathlib.Path(__file__).with_name("CansKey.pem"),
        )

        async with ws.serve(
            ws_handler=self.ConnectionHandler,
            host=host,
            port=int(port),
            ssl=sslContext,
        ):
            await stopAwaitable


if __name__ == "__main__":
    Server()
