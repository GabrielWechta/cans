"""Dummy client application."""

import asyncio
import os

import websockets as ws


async def main() -> None:
    """Continue pinging the server."""
    async with ws.connect(
        f"ws://cans-server:{os.environ.get('CANS_PORT')}"
    ) as sock:
        print("Client entering a sending loop...")
        while True:
            await sock.send("wow, cans!")
            response = await sock.recv()
            print(f"Client got response: {response}")
            await asyncio.sleep(5)


asyncio.run(main())
