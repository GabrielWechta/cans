"""CANS communicator frontend."""

import asyncio
import logging
import logging.handlers
import os
from datetime import datetime

from blessed import Terminal
from olm import OlmAccountError
from peewee import DatabaseError

from common.keys import digest_key
from common.messages import CansMsgId, ShareFriend

from .backup_files import attempt_decrypting_priv_key_backup_files
from .database_manager_client import DatabaseManager
from .models import CansMessageState, Friend, Message
from .session_manager_client import SessionManager
from .startup import Startup
from .user_interface import UserInterface
from .user_interface.state_machines import PasswordRecoveryState, StartupState


class Client:
    """Frontend application starter."""

    def __init__(self) -> None:
        """Construct the client object."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]

        self._do_logger_config()
        self.log = logging.getLogger("cans-logger")
        self.startup = Startup()

        self.event_loop = asyncio.get_event_loop()
        self.db_manager = DatabaseManager(
            name=str(self.startup.db_path),
        )

        assert StartupState

        self.ui = UserInterface(
            loop=self.event_loop,
            input_callbacks={
                "upstream_message": self._handle_upstream_message,
                "graceful_shutdown": self._do_graceful_shutdown,
                "share_friend": self._send_share_friend_message,
                "add_friend": self._add_friend,
            },
            db_manager=self.db_manager,
        )

        # Check if necessary files exist
        if self.startup.is_first_startup():
            # Prompt user for username, password etc in blocking mode
            (
                user_username,
                user_passphrase,
                user_color,
            ) = self.ui.early_prompt_startup()

            # if anything needs to be changed, just do:
            # user_username, _, _ = self.ui.early_prompt(
            #                           state=StartupState.PROMPT_USERNAME,
            #                           isolate_state=True,
            #                           feedback="Error message here!")
            #

            self.password = self.startup.get_key(user_passphrase)
            self.startup.cans_setup()
            self.startup.generate_private_key(self.password)
            self.priv_key, self.pub_key = self.startup.load_key_pair(
                self.password
            )

            self.app_password = self.startup.get_app_password(self.priv_key)

            self.account = self.startup.create_crypto_account(
                self.app_password
            )

            # init db manager
            self.db_manager.open(passphrase=self.app_password)

            # Initialize system and myself in the database
            self.system = self.db_manager.add_friend(
                Friend(
                    id="system", username="System", color="orange_underline"
                )
            )
            self.myself = self.db_manager.add_friend(
                Friend(id="myself", username=user_username, color=user_color)
            )

            mnemonics = self.startup.generate_mnemonics(count=6, char_length=8)
            self.startup.produce_priv_key_backup_files(
                priv_key=self.priv_key, mnemonics=mnemonics
            )

            self.ui.show_mnemonics(mnemonics)

        # handle consecutive startups
        else:
            feedback = ""
            retries = 3
            password_needed = False

            try:
                self.password = self.startup.get_key()
                self._load_data(password=self.password)
            except Exception as e:
                self.log.debug(f"{e}")
                password_needed = True

            while password_needed:
                user_passphrase = self.ui.blocking_prompt(
                    "password", feedback=feedback
                )

                # Password recovery needed here:
                if user_passphrase == "~":
                    mnemonic = self.ui.blocking_prompt(
                        PasswordRecoveryState.PROMPT_MNEMONIC
                    )
                    (
                        successful,
                        empty,
                        priv_key,
                    ) = attempt_decrypting_priv_key_backup_files(
                        alleged_mnemonic=mnemonic,
                        backups_dir_path=self.startup.backups_dir,
                        load_dec_func=self.startup.decrypt_from_disk,
                    )

                    if successful:
                        feedback = "Password changed."
                        new_passphrase = self.ui.blocking_prompt(
                            PasswordRecoveryState.PROMPT_NEW_PASSWORD,
                        )
                        password = self.startup.get_key(new_passphrase)
                        self.startup.encrypt_on_disk(
                            plaintext=priv_key,  # type: ignore
                            path=str(self.startup.user_private_key_path),
                            key=password,
                        )

                        continue  # check if user typed password correctly
                    elif empty:
                        feedback = "No backup files remaining. Tough luck."
                        continue
                    else:
                        feedback = "Bad one time password provided."
                        continue

                self.password = self.startup.get_key(user_passphrase)

                try:
                    self._load_data(password=self.password)
                except ValueError as e:
                    # Corrupted keys or wrong password
                    if retries > 0:
                        retries = retries - 1
                        feedback = "Wrong password."
                        continue
                    else:
                        self.log.critical(f"Can't decrypt keys: {e}")
                        self.event_loop.run_until_complete(
                            self._do_graceful_shutdown()
                        )
                except DatabaseError as e1:
                    self.log.critical(f"Database Error: {e1}")
                    self.event_loop.run_until_complete(
                        self._do_graceful_shutdown()
                    )
                except OlmAccountError as e2:
                    self.log.critical(f"Corrupted OlmAccount: {e2}")
                    self.event_loop.run_until_complete(
                        self._do_graceful_shutdown()
                    )

                break

        # Complete UI startup
        assert self.myself and self.system
        self.ui.set_identity_user(self.myself)
        self.ui.set_system_user(self.system)

        self.ui.complete_startup()
        self.ui.set_self_user_id(digest_key(self.pub_key))

        # Fetch friends' IDs from the database
        self.friends = {
            friend.id for friend in self.db_manager.get_all_friends()
        }

        self.session_manager = SessionManager(
            keys=(self.priv_key, self.pub_key),
            account=self.account,
        )

    def run(self) -> None:
        """Run dummy client application."""
        try:
            self.event_loop.run_until_complete(
                asyncio.gather(  # noqa: FKA01
                    # Connect to the server...
                    self.session_manager.connect(
                        url=f"wss://{self.server_hostname}:{self.server_port}",
                        certpath=self.certpath,
                        friends=self.friends,
                    ),
                    # ...and handle incoming messages
                    self._handle_downstream_user_traffic(),
                    self._handle_downstream_system_traffic(),
                )
            )
        except Exception as e:
            self.log.critical(
                f"Fatal exception ({type(e).__name__}): {str(e)}"
            )
            self.event_loop.run_until_complete(self._do_graceful_shutdown())

    def _load_data(self, password: str = "") -> None:
        """Load database and keys to the client."""
        self.priv_key, self.pub_key = self.startup.load_key_pair(password)

        self.app_password = self.startup.get_app_password(self.priv_key)

        # init db manager
        self.db_manager.open(passphrase=self.app_password)

        self.system = self.db_manager.get_friend(id="system")
        self.myself = self.db_manager.get_friend(id="myself")

        self.account = self.startup.load_crypto_account(self.app_password)

    async def _handle_downstream_user_traffic(self) -> None:
        """Handle downstream user messages."""
        while True:
            message = await self.session_manager.receive_user_message()

            self.log.debug(f"Received message from {message.header.sender}")

            # TODO: Add support for message from unknown user
            assert self.myself
            self.db_manager.save_message(
                id=message.payload["cookie"],
                body=message.payload["text"],
                date=datetime.now(),
                state=CansMessageState.DELIVERED,
                from_user=message.header.sender,
                to_user=self.myself.id,
            )

            # Forward to UI
            self.ui.on_new_message_received(
                message.payload["text"], message.header.sender
            )

    async def _handle_downstream_system_traffic(self) -> None:
        """Handle downstream server messages."""
        while True:
            message = await self.session_manager.receive_system_message()
            if message.header.msg_id == CansMsgId.PEER_LOGIN:
                # TODO: Make it more general
                payload = Terminal().green_underline("User just logged in!")
                self.ui.on_system_message_received(
                    payload, message.payload["peer"]
                )
            elif message.header.msg_id == CansMsgId.PEER_LOGOUT:
                # TODO: Make it more general
                payload = Terminal().red_underline("User just logged out!")
                self.ui.on_system_message_received(
                    payload, message.payload["peer"]
                )
            elif message.header.msg_id == CansMsgId.SHARE_FRIEND:
                self.ui.handle_friend_sharing(
                    sender=message.header.sender,
                    friend_id=message.payload["friend"],
                    local_name=message.payload["name"],
                )
            elif message.header.msg_id == CansMsgId.ACK_MESSAGE_DELIVERED:
                self.ui.view.update_message_status(
                    chat_with=message.header.sender,
                    id=message.payload["cookie"],
                    status=CansMessageState.DELIVERED,
                )
                is_successful = self.db_manager.update_message(
                    id=message.payload["cookie"],
                    state=CansMessageState.DELIVERED,
                )
                # potential malicious ack message
                if not is_successful:
                    self.log.error(
                        "Unexpected ACK for message "
                        + f"{message.payload['cookie']} from "
                        + f"{message.header.sender}"
                    )
            elif message.header.msg_id == CansMsgId.NACK_MESSAGE_NOT_DELIVERED:
                payload = Terminal().silver("User is unavailable")
                self.ui.on_system_message_received(
                    payload, message.payload["peer"]
                )
            else:
                self.log.error(
                    "Received unsupported system message"
                    + f" {message.header.msg_id}"
                )

    async def _handle_upstream_message(self, message_model: Message) -> None:
        """Handle an upstream message."""
        receiver = message_model.to_user
        message, cookie = self.session_manager.user_message_to(
            receiver.id, message_model.body
        )
        message_model.id = cookie
        self.db_manager.save_message(message_model)
        self.ui.view.add_message(
            receiver, message_model  # type: ignore
        )  # type: ignore

        self.log.debug(
            f"Sending message to {message.header.receiver}"
            + f" (cookie: {cookie})..."
        )

        await self.session_manager.send_message(message)

    async def _send_share_friend_message(
        self, receiver: str, shared_friend: Friend
    ) -> None:
        """Send a friend sharing message."""
        message = ShareFriend(
            receiver=receiver,
            shared_friend=shared_friend.id,
            local_name=shared_friend.username,
        )

        self.log.debug(
            f"Sending ShareFriend message to {receiver}"
            + f" (Shared friend: {shared_friend.id})..."
        )

        await self.session_manager.send_message(message)

    async def _add_friend(self, friend: Friend) -> None:
        """Add a friend at session manager level."""
        await self.session_manager.add_friend(friend.id)

    async def _do_graceful_shutdown(self) -> None:
        """Shut down the application gracefully."""
        self.log.info("Shutting the blinds...")
        if hasattr(self, "session_manager"):
            await self.session_manager.shutdown()
        self.log.info("Locking the door...")
        if hasattr(self, "db_manager"):
            self.db_manager.close()
        self.log.info("Hanging the 'closed' sign in the window...")
        self.ui.shutdown()
        self.log.info("Bye, bye...")
        os._exit(0)

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
