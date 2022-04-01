"""Dummy client application."""

import asyncio
import os
import pathlib
import ssl

import websockets.client as ws


class Client:
    """Dummy client class."""

    def __init__(self) -> None:
        """Construct the client."""
        asyncio.run(self.RunDummyClient())

    async def RunDummyClient(self) -> None:
        """Connect to the server repeatedly and get a response."""
        host = os.environ["CANS_SERVER_HOSTNAME"]
        port = os.environ["CANS_PORT"]
        sslContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        sslContext.load_verify_locations(
            # Trust the self-signed certificate for PoC purposes
            pathlib.Path(__file__).with_name("CansCert.pem")
        )
        while True:
            print("Connecting to the server...")
            async with ws.connect(
                f"wss://{host}:{port}", ssl=sslContext
            ) as conn:
                resp = await conn.recv()
                print("Client received: " + str(resp))
            await asyncio.sleep(3)


if __name__ == "__main__":
    Client()
