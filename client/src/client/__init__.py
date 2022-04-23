"""CANS communicator frontend."""

import asyncio
import hashlib
import os
from datetime import datetime

from olm import Account

from common.keys import PubKeyDigest

from .database_manager_client import DatabaseManager
from .models import MessageModel, UserModel
from .osal import OSAL
from .session_manager_client import SessionManager
from .user_interface import UserInterface


class Client:
    """Frontend application starter."""

    def __init__(self, identity: PubKeyDigest) -> None:
        """Construct the client object."""
        # TODO: Parse environment variables
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]
        self.osal = OSAL()
        print(f"HWF: {self.osal.hardware_fingerprint()}")

        self._do_logger_config()

        # TODO: Try early startup (decryption of keys, database access etc.)?
        #       Either way a later startup will need to be supported as user
        #       input may be required (password)

        # TODO: Do application initialization (create directories, keys etc.)
        #       if the user logs in for the first time (some crude UI will
        #       be needed here)

        self.event_loop = asyncio.get_event_loop()
        self.db_manager = DatabaseManager()

        self.ui = UserInterface(self.event_loop)
        bob = UserModel(
            username="Bob",
            id=hashlib.md5("aa".encode("utf-8")).hexdigest(),
            color="pink",
        )

        system = UserModel(
            username="System",
            id=hashlib.md5("system".encode("utf-8")).hexdigest(),
            color="orange_underline",
        )
        # set identity
        self.myself = UserModel(username="Alice", id="123", color="green")

        self.ui.view.add_chat(bob)
        self.ui.view.add_chat(bob)
        self.ui.view.add_chat(bob)

        message = MessageModel(
            date=datetime.now(),
            body="test",
            from_user=system,
            to_user=self.myself,
        )

        self.ui.on_new_message_received(message, bob)
        # TODO: During early startup pickled olm.Account should be un-pickled
        #       and passed to TripleDiffieHellmanInterface and SessionManager
        account = Account()

        # Session manager is the last needed component
        self.session_manager = SessionManager(
            keys=(identity, identity),  # TODO: Add public/private key pair
            account=account,
        )

    def run(self) -> None:
        """Run the client application."""
        # Connect to the server
        self.event_loop.run_until_complete(
            self.session_manager.connect(
                url=f"wss://{self.server_hostname}:{self.server_port}",
                certpath=self.certpath,
                friends=["cans-echo-service"],
            )
        )

    def _do_logger_config(self) -> None:
        """Initialize the logger."""
        # TODO: Implement me!
