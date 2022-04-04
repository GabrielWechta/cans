"""Main backend application entry point."""

import asyncio
import os

from ConnectionListener import ConnectionListener


class Server:
    """Backend application starter."""

    def __init__(self) -> None:
        """Construct the server object."""
        # Parse environment variables
        self.hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.port = int(os.environ["CANS_PORT"])

        # Prepare resources
        self.event_loop = asyncio.get_event_loop()
        self.connection_listener = ConnectionListener(self.hostname, self.port)

    def run(self) -> None:
        """Run the connection listener."""
        self.event_loop.run_until_complete(self.connection_listener.run())


if __name__ == "__main__":
    server = Server()
    server.run()
