"""Client connection entry point.

Listen for connection on a public port and dispatch
them to connection handlers/callbacks.
"""

import asyncio
import logging
import ssl

import websockets.server as ws
from exceptions.CansServerAuthFailed import CansServerAuthFailed
from SessionManager import SessionManager

from common.types.PubKey import PubKey, PubKeyDigest


class ConnectionListener:
    """Listen on a public port and authenticate incoming clients."""

    def __init__(self, hostname: str, port: int) -> None:
        """Construct a connection listener instance."""
        self.hostname = hostname
        self.port = port
        self.session_manager = SessionManager()
        self.log = logging.getLogger("cans-logger")

    async def run(self) -> None:
        """Open a public port and listen for connections."""
        self.log.info(f"Hostname is {self.hostname}")

        sslContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        sslContext.load_cert_chain(
            # TODO: Resolve the certificate and key paths dynamically using
            # e.g. .env file (at least serverside, client uses the local
            # self-signed cert only for proof-of-concept purposes anyway)
            certfile="certs/CansCert.pem",
            keyfile="certs/CansKey.pem",
        )

        self.log.info(
            f"SSL context established. Opening public port: {self.port}..."
        )

        async with ws.serve(
            ws_handler=self.__handle_connection,
            host=self.hostname,
            port=self.port,
            ssl=sslContext,
        ):
            # TODO: Implement graceful shutdown
            await asyncio.Future()

    async def __handle_connection(
        self, conn: ws.WebSocketServerProtocol
    ) -> None:
        """Handle a new incoming connection."""
        self.log.debug(
            f"Accepted connection from {conn.remote_address[0]}:"
            f"{conn.remote_address[1]}"
        )

        # Authenticate the user
        try:
            public_key = await self.__authenticate_user(conn)
            public_key_digest = self.__digest_key(public_key)
            self.log.debug(
                f"Successfully authenticated user at {conn.remote_address[0]}:"
                + f"{conn.remote_address[1]} with public key {public_key}"
                + f" (digest: {public_key_digest})"
            )
            # User has been successfully authenticated,
            # delegate further handling to the session
            # manager
            await self.session_manager.authed_user_entry(
                conn, public_key_digest
            )
        except CansServerAuthFailed:
            self.log.error(
                f"User authentication failed: {conn.remote_address[0]}:"
                + f"{conn.remote_address[1]}"
            )
            return

    async def __authenticate_user(
        self, conn: ws.WebSocketServerProtocol
    ) -> PubKey:
        """Run authentication protocol with the user."""
        self.log.error(
            f"__authenticate_user{conn.remote_address}: Implement me!"
        )
        # TODO: Get the public key from the user as well as proof of
        #       knowledge of the corresponding private key

        # NOTE: In the alpha-version user simply sends their public key
        # with no further auth
        public_key = await conn.recv()
        return str(public_key)

    def __digest_key(self, public_key: PubKey) -> PubKeyDigest:
        # TODO: Call src/common code to calculate the hash over the key
        return public_key
