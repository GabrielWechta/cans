"""Dummy client application."""

import asyncio
import json
import os
import pathlib
import ssl
import sys

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
        print("Connecting to the server...")
        async with ws.connect(f"wss://{host}:{port}", ssl=sslContext) as conn:

            # NOTE: For PoC purposes get a mock public_key
            # from the command line
            name = sys.argv[1]
            public_key = sys.argv[2]
            peer_key = sys.argv[3]

            print(
                f"This is {name}. My public key is {public_key}. "
                + "Authenticating..."
            )

            # TODO: Authenticate to the server
            await conn.send(public_key)

            poc_message = {
                "sender": public_key,
                "receiver": peer_key,
                "payload": f"Hello neighbour at {peer_key}",
            }

            if "Alice" in public_key:
                await asyncio.sleep(5)

            while True:
                await conn.send(json.JSONEncoder().encode(poc_message))

                resp = json.JSONDecoder().decode(str(await conn.recv()))
                sender = resp["sender"]
                payload = resp["payload"]
                print(f"{name} received message '{payload}' from {sender}")

                await asyncio.sleep(1)


if __name__ == "__main__":
    Client()
