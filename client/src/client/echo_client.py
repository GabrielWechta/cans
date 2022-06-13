"""Echo client service."""
import asyncio
import os

from olm import Account

from .session_manager_client import SessionManager


class EchoClient:
    """Echo client service."""

    def __init__(self) -> None:
        """Run an echo client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]

        self.event_loop = asyncio.get_event_loop()

        account = Account()

        private_key = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIJtHyoESBz5C0dZaWH0ILVh6912SoNtQ0u1HqUmjg3aeoAoGCCqGSM49
AwEHoUQDQgAEW7zs8m7vx15kt1YFYobo9qL7jMqsksLiCIUdTgUnbpVQm7sZQnc5
4QPzNZGPbxZe7BPhzlNhnuQyHDZ/0Ij6QA==
-----END EC PRIVATE KEY-----
"""
        public_key = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEW7zs8m7vx15kt1YFYobo9qL7jMqs
ksLiCIUdTgUnbpVQm7sZQnc54QPzNZGPbxZe7BPhzlNhnuQyHDZ/0Ij6QA==
-----END PUBLIC KEY-----
"""

        self.session_manager = SessionManager(
            keys=(private_key, public_key),
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
                    friends=set(),
                ),
                self._echo_service(),
                self._cplane_sink(),
            )
        )

    async def _echo_service(self) -> None:
        """Implement the echo service."""
        while True:
            request = await self.session_manager.receive_user_message()
            # Echo the message back
            sender = request.header.sender
            response, _ = self.session_manager.user_message_to(
                sender, request.payload["text"]
            )
            await self.session_manager.send_message(response)

    async def _cplane_sink(self) -> None:
        """Drop control messages received by the echo service."""
        while True:
            message = await self.session_manager.receive_system_message()
            message = message


if __name__ == "__main__":
    client = EchoClient()
    client.run()
