"""Main backend application entry point."""

import asyncio
import logging
import logging.handlers
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
        self.__do_logger_config()
        self.event_loop = asyncio.get_event_loop()
        self.connection_listener = ConnectionListener(self.hostname, self.port)

    def run(self) -> None:
        """Run the connection listener."""
        self.event_loop.run_until_complete(self.connection_listener.run())

    def __do_logger_config(self) -> None:
        """Initialize the logger."""
        logger = logging.getLogger("cans-logger")

        # Prepare the formatter
        formatter = logging.Formatter(
            fmt="[%(levelname)s] %(asctime)s %(message)s",
        )

        # Create a rotating file handler
        handler = logging.handlers.RotatingFileHandler(
            filename=os.environ["CANS_LOGFILE_PATH"],
            maxBytes=int(os.environ["CANS_LOGFILE_CAPACITY_KB"]) * 1024,
        )

        # Associate the formatter with the handler...
        handler.setFormatter(formatter)
        # ...and the handler with the logger
        logger.addHandler(handler)

        logger.setLevel(logging.INFO)
        # NOTE: Uncomment to enable debug logging during development
        # logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    server = Server()
    server.run()
