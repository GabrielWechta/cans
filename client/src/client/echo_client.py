"""Echo client service."""
import asyncio
import os
import sys

from olm import Account

from common.keys import PubKeyDigest

from .session_manager_client import SessionManager


class EchoClient:
    """Echo client service."""

    def __init__(self, identity: PubKeyDigest) -> None:
        """Run an echo client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]

        self.event_loop = asyncio.get_event_loop()

        account = Account()

        self.session_manager = SessionManager(
            keys=(identity, identity),
            account=account,
        )

    def run(self) -> None:
        """Run the echo client service."""
        # Connect to the server
        self.event_loop.run_until_complete(
            asyncio.gather(  # noqa: FKA01
                self.session_manager.connect(
                    url=f"wss://{self.server_hostname}:{self.server_port}",
                    certpath=self.certpath,
                    friends=[],
                ),
                self._echo_service(),
                self._cplane_sink(),
            )
        )

    async def _echo_service(self) -> None:
        """Implement the echo service."""
        while True:
            message = await self.session_manager.receive_user_message()
            # Swap sender and receiver
            sender = message.header.sender
            receiver = message.header.receiver
            message.header.sender = receiver
            message.header.receiver = sender
            # Echo the message back
            await self.session_manager.send_message(message)

    async def _cplane_sink(self) -> None:
        """Drop control messages received by the echo service."""
        while True:
            message = await self.session_manager.receive_system_message()
            message = message


if __name__ == "__main__":
    if len(sys.argv) > 1:
        identity = sys.argv[1]
    else:
        identity = "cans-echo-service"

    client = EchoClient(identity)
    client.run()
