"""CANS communicator frontend."""

import asyncio
import logging
import logging.handlers
import os

from blessed import Terminal

from common.keys import digest_key
from common.messages import CansMsgId

from .database_manager_client import DatabaseManager
from .models import MessageModel, UserModel
from .session_manager_client import SessionManager
from .startup import Startup
from .user_interface import UserInterface


class Client:
    """Frontend application starter."""

    def __init__(self) -> None:
        """Construct the client object."""
        # TODO: Parse environment variables
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]

        self._do_logger_config()
        self.log = logging.getLogger("cans-logger")
        self.startup = Startup()

        # TODO: Implement proper password prompts during startup
        # Check if necessary files exist
        if self.startup.is_first_startup():
            user_passphrase = "SafeAndSecurePassword2137"
            self.password = self.startup.get_password(user_passphrase)
            self.startup.cans_setup()
            self.pub_key, self.priv_key = self.startup.generate_key_pair(
                self.password
            )
            self.account = self.startup.create_crypto_account(self.password)
        else:
            user_passphrase = "SafeAndSecurePassword2137"
            self.password = self.startup.get_password(user_passphrase)
            self.pub_key, self.priv_key = self.startup.decrypt_key_pair(
                self.password
            )
            self.account = self.startup.load_crypto_account(self.password)

        self.event_loop = asyncio.get_event_loop()
        self.db_manager = DatabaseManager()

        # TODO: Remove hardcoded identity
        pub_key = "AlicePubKey"
        priv_key = "AlicePrivKey"
        # set identity
        self.myself = UserModel(
            username="Alice", id=digest_key(pub_key), color="blue"
        )
        echo_client = UserModel(
            username="Echo", id="cans-echo-service", color="red"
        )
        bob_client = UserModel(username="Bob", id="bob_key", color="orange")
        eve_client = UserModel(username="Eve", id="eve_key", color="purple")
        # offline_client = UserModel(
        #    username="Sleepy", id="doesnt exits", color="yellow"
        # )

        self.ui = UserInterface(
            loop=self.event_loop,
            upstream_callback=self._handle_upstream_message,
            identity=self.myself,
        )

        self.ui.view.add_chat(echo_client)
        self.ui.view.add_chat(bob_client)
        self.ui.view.add_chat(eve_client)
        self.ui.view.add_chat(echo_client)
        # self.ui.view.add_chat(offline_client)

        self.session_manager = SessionManager(
            keys=(pub_key, priv_key),
            account=self.account,
        )

    def run(self) -> None:
        """Run dummy client application."""
        # Connect to the server
        self.event_loop.run_until_complete(
            asyncio.gather(  # noqa: FKA01
                self.session_manager.connect(
                    url=f"wss://{self.server_hostname}:{self.server_port}",
                    certpath=self.certpath,
                    friends=["cans-echo-service", "eve_key", "bob_key"],
                ),
                self._handle_downstream_user_traffic(),
                self._handle_downstream_system_traffic(),
            )
        )

    async def _handle_downstream_user_traffic(self) -> None:
        """Handle downstream user messages."""
        while True:
            message = await self.session_manager.receive_user_message()

            self.log.debug(f"Received message from {message.header.sender}")

            # TODO: Add message to database

            # Forward to UI
            self.ui.on_new_message_received(
                message.payload, message.header.sender
            )

    async def _handle_downstream_system_traffic(self) -> None:
        """Handle downstream server messages."""
        while True:
            message = await self.session_manager.receive_system_message()
            if message.header.msg_id == CansMsgId.PEER_LOGIN:
                # TODO: make it more general
                payload = Terminal().green_underline("User just logged in!")
                self.ui.on_system_message_received(
                    payload, message.payload["peer"]
                )
            elif message.header.msg_id == CansMsgId.PEER_LOGOUT:
                # TODO: make it more general
                payload = Terminal().red_underline("User just logged out!")
                self.ui.on_system_message_received(
                    payload, message.payload["peer"]
                )
            elif message.header.msg_id == CansMsgId.PEER_UNAVAILABLE:
                payload = Terminal().silver("User is unavailable")
                self.ui.on_system_message_received(
                    payload, message.payload["peer"]
                )
            else:
                self.log.error(
                    "Received unsupported system message"
                    + f" {message.header.msg_id}"
                )

    async def _handle_upstream_message(
        self, message_model: MessageModel
    ) -> None:
        """Handle an upstream message."""
        receiver = message_model.to_user
        message = self.session_manager.user_message_to(
            receiver.id, message_model.body
        )

        self.log.debug(f"Sending message to {message.header.receiver}...")

        await self.session_manager.send_message(message)

    def _do_logger_config(self) -> None:
        """Initialize the logger."""
        logger = logging.getLogger("cans-logger")

        # Prepare the formatter
        formatter = logging.Formatter(
            fmt="[%(levelname)s] %(asctime)s %(message)s",
        )

        # Create a rotating file handler
        handler = logging.handlers.RotatingFileHandler(
            filename=os.environ["CANS_CLIENT_LOGFILE_PATH"],
            maxBytes=int(os.environ["CANS_CLIENT_LOGFILE_CAPACITY_KB"]) * 1024,
        )

        # Associate the formatter with the handler...
        handler.setFormatter(formatter)
        # ...and the handler with the logger
        logger.addHandler(handler)

        logger.setLevel(logging.INFO)
        # NOTE: Uncomment to enable debug logging during development
        # logger.setLevel(logging.DEBUG)
