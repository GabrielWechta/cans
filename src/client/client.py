"""Dummy client application."""

import asyncio
import os

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
        while True:
            print("Connecting to the server...")
            async with ws.connect(
                f"ws://{host}:{port}",
            ) as conn:
                resp = await conn.recv()
                print("Client received: " + str(resp))
            await asyncio.sleep(3)


if __name__ == "__main__":
    Client()
