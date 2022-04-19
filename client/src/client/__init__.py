"""CANS communicator frontend."""

import asyncio
import os

from common.keys import PubKeyDigest

from .database_manager_client import DatabaseManager
from .key_manager import KeyManager
from .osal import OSAL
from .session_manager_client import SessionManager
from .user_interface import UserInterface


class Client:
    """Frontend application starter."""

    def __init__(
        self, identity: PubKeyDigest, hardcoded_peer: PubKeyDigest
    ) -> None:
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

        self.ui = UserInterface()

        self.event_loop = asyncio.get_event_loop()
        self.key_manager = KeyManager(identity)
        self.db_manager = DatabaseManager()

        # TODO: During early startup pickled olm.Account should be un-pickled
        #       and passed to TripleDiffieHellmanInterface and SessionManager

        self.tdh_interface = TripleDiffieHellmanInterface()

        # Session manager is the last needed component
        # TODO: Perhaps resolve this dependency more cleanly or get rid of it
        self.session_manager = SessionManager(
            key_manager=self.key_manager, hardcoded_peer=hardcoded_peer
        )

    def run(self) -> None:
        """Run the client application."""
        # TODO: Run late startup: prompt the user for password etc.

        # Connect to the server
        self.event_loop.run_until_complete(
            self.session_manager.connect(
                url=f"wss://{self.server_hostname}:{self.server_port}",
                certpath=self.certpath,
            )
        )

    def _do_logger_config(self) -> None:
        """Initialize the logger."""
        # TODO: Implement me!
