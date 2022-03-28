"""Dummy server application."""

import asyncio
import os

import websockets as ws


async def echo(sock: ws.WebSocketServerProtocol) -> None:
    """Echo the message back to the client."""
    print("Server opening the socket...")
    async for message in sock:
        print(f"Server got message: {message}")
        await sock.send(message)


async def main() -> None:
    """Run a WebSockets echo server."""
    async with ws.serve(
        ws_handler=echo, host="cans-server", port=os.environ.get("CANS_PORT")
    ):
        await asyncio.Future()


asyncio.run(main())
