"""Client connection entry point.

Listen for connection on a public port and dispatch
them to connection handlers/callbacks.
"""

import asyncio
import logging
import ssl
from typing import Dict, Set, Tuple

import websockets.server as ws
from cans_common.connection import CansStatusCode
from cans_common.keys import digest_key, get_schnorr_challenge, schnorr_verify
from cans_common.messages import (
    CansMessageException,
    SchnorrChallenge,
    SchnorrCommit,
    SchnorrResponse,
    cans_recv,
    cans_send,
)

from .session_manager_server import SessionManager


class CansServerAuthFailed(Exception):
    """Error thrown on authentication failure."""

    pass


class ConnectionListener:
    """Listen on a public port and authenticate incoming clients."""

    def __init__(
        self, hostname: str, port: int, certpath: str, keypath: str
    ) -> None:
        """Construct a connection listener instance."""
        self.hostname = hostname
        self.port = port
        self.certpath = certpath
        self.keypath = keypath
        self.session_manager = SessionManager()
        self.log = logging.getLogger("cans-logger")

    async def run(self) -> None:
        """Open a public port and listen for connections."""
        self.log.info(f"Hostname is {self.hostname}")

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(
            certfile=self.certpath,
            keyfile=self.keypath,
        )

        self.log.info(
            f"SSL context established. Opening public port: {self.port}..."
        )

        async with ws.serve(
            ws_handler=self.__handle_connection,
            host=self.hostname,
            port=self.port,
            ssl=ssl_context,
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
            (
                public_key,
                subscriptions,
                identity_key,
                one_time_keys,
            ) = await self.__authenticate_user(conn)
            user_id = digest_key(public_key)
            self.log.debug(
                f"Successfully authenticated user at {conn.remote_address[0]}:"
                + f"{conn.remote_address[1]} with public key {public_key}"
                + f" (digest: {user_id})"
            )
            # User has been successfully authenticated,
            # delegate further handling to the session
            # manager
            await self.session_manager.authed_user_entry(
                conn=conn,
                user_id=user_id,
                subscriptions=subscriptions,
                identity_key=identity_key,
                one_time_keys=one_time_keys,
            )
        except CansServerAuthFailed:
            self.log.error(
                f"User authentication failed: {conn.remote_address[0]}:"
                + f"{conn.remote_address[1]}"
            )
            await conn.close(
                code=CansStatusCode.AUTH_FAILURE,
                reason="Authentication failed",
            )
        except (
            CansMessageException,
            AttributeError,
            KeyError,
            ValueError,
        ) as e:
            self.log.error(
                f"{type(e).__name__} raised when establishing session with"
                + f" {conn.remote_address[0]}:{conn.remote_address[1]}:"
                + f" {str(e)}"
            )
            await conn.close(
                code=CansStatusCode.MALFORMED_MESSAGE,
                reason="Malformed message",
            )
        except Exception as e:
            self.log.error(
                f"User {conn.remote_address[0]}:{conn.remote_address[1]}"
                + " triggered an unexepected exception"
                + f" ({type(e).__name__}): {str(e)}"
            )
            await conn.close(
                code=CansStatusCode.EXCEPTION_RAISED,
                reason="Serverside exception",
            )

    async def __authenticate_user(
        self, conn: ws.WebSocketServerProtocol
    ) -> Tuple[str, Set[str], str, Dict[str, str]]:
        """Run authentication protocol with the user."""
        # Await commitment message
        commit_message: SchnorrCommit = await cans_recv(conn)
        public_key = str(commit_message.payload["public_key"])
        commitment = str(commit_message.payload["commitment"])

        # Send back the challenge
        challenge = get_schnorr_challenge()
        challenge_message = SchnorrChallenge(challenge)
        await cans_send(challenge_message, conn)

        # Wait for the response
        response_message: SchnorrResponse = await cans_recv(conn)
        response = int(response_message.payload["response"])

        if schnorr_verify(
            public_key=public_key,
            commitment=commitment,
            challenge=challenge,
            response=response,
        ):
            return (
                public_key,
                set(response_message.payload["subscriptions"]),
                response_message.payload["identity_key"],
                response_message.payload["one_time_keys"],
            )
        else:
            raise CansServerAuthFailed("Authentication failed!")
