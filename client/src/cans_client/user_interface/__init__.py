"""CANS application UI."""
import asyncio
import inspect
from collections import namedtuple
from datetime import datetime
from random import choice
from typing import Any, Callable, List, Mapping, Optional, Union

import pyperclip
from blessed import Terminal
from blessed.formatters import FormattingString

from ..database_manager_client import DatabaseManager
from ..models import CansMessageState, Friend, Message
from .input import InputMode
from .state_machines import PasswordRecoveryState, StartupState, StateMachine
from .tiles import ChatTile, PromptTile, Tile
from .view import View

PromptConfig = namedtuple("PromptConfig", "title prompt validation mask_input")
Config = namedtuple("Config", "username passphrase color")
CommandConfig = namedtuple("CommandConfig", "callback description")


class UserInterface:
    """CANS application UI."""

    def __init__(
        self,
        loop: Union[asyncio.BaseEventLoop, asyncio.AbstractEventLoop],
        input_callbacks: Mapping[str, Callable],
        db_manager: DatabaseManager,
    ) -> None:
        """Instantiate a UI."""
        # Set terminal and event loop
        self.term = Terminal()
        self.loop = loop
        self.db_manager = db_manager

        # Enter fullscreen mode
        print(self.term.enter_fullscreen, end="")

        # Store the client callbacks
        self.input_callbacks = input_callbacks

        # Instantiate a view
        self.view = View(
            term=self.term,
            loop=self.loop,
            db_manager=self.db_manager,
        )

        # start user input handler
        self.loop.create_task(self._handle_user_input())
        self.cmds_layout: Mapping[Any, Callable[..., Optional[str]]] = {
            # arrow keys
            self.term.KEY_LEFT:  self.view.layout.cmd_left,
            self.term.KEY_RIGHT: self.view.layout.cmd_right,
            self.term.KEY_DOWN:  self.view.layout.cmd_down,
            self.term.KEY_UP:    self.view.layout.cmd_up,

            # arrow keys with shift
            self.term.KEY_SLEFT:     self.view.layout.cmd_swap_left,
            self.term.KEY_SRIGHT:    self.view.layout.cmd_swap_right,
            self.term.KEY_SDOWN:     self.view.layout.cmd_shuffle_down,
            self.term.KEY_SUP:       self.view.layout.cmd_shuffle_up,

            # normal letters
            ' ': self.view.layout.cmd_flip,
            'q': self.view.layout.cmd_grow,
            'w': self.view.layout.cmd_shrink,
            'e': self.view.layout.cmd_normalize,
            'r': self.view.layout.cmd_maximize,

            # ctrl+a
            chr(1):     self.reopen_tile,
            # ctrl+d
            chr(4):     self.close_tile,
        }  # fmt: skip
        """Key mapping for layout changing commands"""

        self.slash_cmds: Mapping[str, CommandConfig] = {
            "chat": CommandConfig(
                self.view.add_chat, "Open new chat box with given user."
            ),
            "sw": CommandConfig(
                self.view.swap_chat,
                "Swap focused chat box with a chat with different user.",
            ),
            "cl": CommandConfig(self.close_tile, "Close focused chat box."),
            "help": CommandConfig(self.show_help, "Show help."),
            "frds": CommandConfig(self.show_friends, "Print friendslist."),
            "add": CommandConfig(
                self.add_friend, "Add new friend from a key."
            ),
            "rm": CommandConfig(
                self.remove_friend, "Remove a friend from friendslist."
            ),
            "key": CommandConfig(
                self.print_pubkey_digest,
                "Print and copy digest of your public key.",
            ),
            "shr": CommandConfig(
                self.share_friend,
                "Share your friend with a user from focused chat box.",
            ),
            "shra": CommandConfig(
                self.share_all_friends,
                f"Share {self.term.bold('all')} your friends with a "
                f"user from focused chat box.",
            ),
        }
        """Mapping for slash commands"""

        dummy = Friend()

        self.myself = dummy
        """Self identity user"""

        self.system_user = dummy
        """System user for system commands"""

        self.prompt_switches = {
            StartupState.PROMPT_USERNAME: PromptConfig(
                title=f"Startup {StartupState.PROMPT_USERNAME.value}"
                " - Set username",
                prompt=f"Welcome to {self.term.red_bold_underline('cans')}! "
                "Please input your username, it can be changed later. "
                "Username cannot contain trailing/leading whitespaces and "
                "cannot be empty.",
                validation=self.validate_username,
                mask_input=False,
            ),
            StartupState.PROMPT_COLOR: PromptConfig(
                title=f"Startup {StartupState.PROMPT_COLOR.value} - Set color",
                prompt="Please input the color you want to "
                "use for your username, "
                "it can be changed later.",
                validation=self.validate_color,
                mask_input=False,
            ),
            StartupState.PROMPT_PASSWORD: PromptConfig(
                title=f"Startup [{StartupState.PROMPT_PASSWORD.value}]"
                " - [Optional] Set password",
                prompt="If you want to have additional protection, input a "
                "password for your account. Password cannot contain any "
                "whitespace characters and if provided it should be at "
                "least 6 characters long.",
                validation=self.validate_password,
                mask_input=True,
            ),
            PasswordRecoveryState.PROMPT_MNEMONIC: PromptConfig(
                title=f"Recovery {PasswordRecoveryState.PROMPT_MNEMONIC.value}"
                " - Input one time password",
                prompt=f"It seems you've {self.term.bold('forgotten')} "
                "your password. To recover your key, please input one of the "
                f"{self.term.green('one time passwords')} that were "
                "generated during registration.",
                validation=self.validate_mnemonic,
                mask_input=False,
            ),
            PasswordRecoveryState.PROMPT_NEW_PASSWORD: PromptConfig(
                title=f"Recovery "
                f"[{PasswordRecoveryState.PROMPT_NEW_PASSWORD.value}]"
                " - [Optional] Set password",
                prompt="If you want to have additional protection, input a "
                "password for your account. Password cannot contain any "
                "whitespace characters and if provided it should be at "
                "least 6 characters long. Please try to remember it this "
                "time.",
                validation=self.validate_password,
                mask_input=True,
            ),
            "password": PromptConfig(
                title="Input password",
                prompt="Please input your password."
                "Input '~' to enter password recovery mode.",
                validation=self.validate_password,
                mask_input=True,
            ),
        }
        """Prompt states in from (title, prompt, validation, mask input?)"""

        self.last_closed_tile: List[Tile] = []

        self.prompt_tile: Optional[PromptTile] = None

        self.loop.run_until_complete(self.create_queue())

        self.loop.create_task(self.view.render_all())

        self.self_user_id: Optional[str] = None

    def share_all_friends(self, peer: Optional[str] = None) -> None:
        """Send friends ids to given user."""
        friends = self.db_manager.get_all_friends()

        for friend in friends:
            try:
                self.share_friend(shared_friend=friend.id, peer=peer)
            except BaseException:
                continue

    def share_friend(
        self, shared_friend: str, peer: Optional[str] = None
    ) -> None:
        """Send friend id to given peer."""
        callback = self.input_callbacks["share_friend"]
        shared_friend_object = self.find_friend_by_id_or_username(
            shared_friend
        )
        if not shared_friend_object:
            raise Exception("Friend not in database.")

        if peer:
            peer_object = self.find_friend_by_id_or_username(peer)
            if peer_object:
                receiver = peer_object.id
        else:
            if isinstance(self.view.layout.current_tile, ChatTile):
                receiver = self.view.layout.current_tile.chat_with.id
            else:
                raise Exception(
                    "If no chat box is focused, [peer] is required"
                )

        if receiver == self.system_user.id:
            raise Exception("Cannot share with system user.")

        if (
            shared_friend_object == self.myself
            or shared_friend_object == self.system_user
        ):
            raise Exception("Cannot share system users.")

        if shared_friend_object.id == receiver:
            raise Exception("Cannot share a friend with himself. Duh.")

        self.loop.create_task(callback(receiver, shared_friend_object))

    def handle_friend_sharing(
        self, sender: str, friend_id: str, local_name: str
    ) -> None:
        """Handle friend sharing request from a peer.

        Wrapper for async operations.
        """
        self.loop.create_task(
            self._handle_friend_sharing(
                sender=sender, friend_id=friend_id, local_name=local_name
            )
        )

    async def _handle_friend_sharing(
        self, sender: str, friend_id: str, local_name: str
    ) -> None:
        """Handle friend sharing request from a peer."""
        sender_object = self.db_manager.get_friend(sender)

        # unknown user
        if not sender_object:
            return

        chats = self.view.find_chats(sender_object)
        if len(chats) == 0:
            self.view.add_chat(chat_with=sender_object)
            chats = self.view.find_chats(sender_object)
        chat = chats[0]

        await chat.is_prompting.acquire()

        username = f"{sender_object.username}.{local_name}"
        key = friend_id

        decision: Optional[bool] = None
        col = sender_object.color

        while decision is None:
            answer = await chat.prompt(
                f"User "
                f"{getattr(self.term, col)(sender_object.username)} "
                f"wants to share his {local_name} contact with you. "
                f"Do you want to accept? y/n",
                self.term,
            )
            if "y" in answer:
                decision = True
            elif "n" in answer:
                decision = False

        color = ""
        if decision:
            try:
                self.add_friend(username=username, key=key, color=color)
            except BaseException as ex:
                self.on_system_message_received(message=self.term.red(str(ex)))

        chat.is_prompting.release()

    def find_friend_by_id_or_username(
        self, id_or_username: str
    ) -> Optional[Friend]:
        """Find user in the database with provided id or username."""
        friend_object = self.db_manager.get_friend(id=id_or_username)
        if not friend_object:
            # username was provided or user not in db
            friend_object = self.get_friend_by_username(id_or_username)
        return friend_object

    def set_self_user_id(self, key: str) -> None:
        """Set given key as identity user's public key."""
        self.self_user_id = key

    def shutdown(self) -> None:
        """Shut down the user interface."""
        self.view.footer.terminate()
        self.view.close_threads()
        print(self.term.exit_fullscreen)

    def set_identity_user(self, identity: Friend) -> None:
        """Set given Friend as myself."""
        self.myself = identity
        self.view.set_identity_user(identity)

    def set_system_user(self, user: Friend) -> None:
        """Set given Friend as system user."""
        self.system_user = user

    def validate_color(self, color: str) -> bool:
        """Validate if given color exists and is safe to use."""
        try:
            color = getattr(self.term, color)
        except AttributeError:
            return False
        # color should always be some string sequence.
        # by doing it this way we give the user option to user underline,
        # bold, reverse, background colors etc.
        # There should be no unsafe Terminal attribute that is
        # a FormattingString, so this **should** be safe
        test = isinstance(color, FormattingString)
        return test

    def validate_password(self, password: str) -> bool:
        """Validate if given password is valid."""
        if password == "" or password == "~":
            return True
        password_without_whitespace = "".join(password.split())
        return password == password_without_whitespace and len(password) >= 6

    def validate_mnemonic(self, mnemonic: str) -> bool:
        """Validate if given mnemonic is valid."""
        mnemonic_without_whitespace = "".join(mnemonic.split())
        return mnemonic == mnemonic_without_whitespace and len(mnemonic) == 8

    def validate_username(self, username: str) -> bool:
        """Validate if given username is valid."""
        if username == "":
            return False
        username_stripped = username.strip()
        return username == username_stripped

    def add_friend(
        self, username: str, key: str = "", color: str = ""
    ) -> None:
        """Add given key to friendslist."""
        if not key and isinstance(self.view.layout.current_tile, ChatTile):
            friend = self.view.layout.current_tile.chat_with
            friends = self.get_friends()
            if friend not in friends and not (
                friend == self.system_user or friend == self.myself
            ):
                key = friend.id
            else:
                raise Exception("Key is required.")
        if not key:
            raise Exception("Key is required.")

        if not color:
            colors = [
                "red",
                "blue",
                "orange",
                "pink",
                "green",
                "purple",
                "brown",
                "yellow",
                "white",
                "salmon",
                "chocolate",
                "webgreen",
                "aquamarine",
                "hotpink",
            ]
            color = choice(colors)

        assert self.validate_color(color), "Color unknown"

        if self.db_manager.get_friend(key):
            # if user already exists
            raise Exception("User with given id already exists!")

        new_user = self.db_manager.add_friend(
            username=username, id=key, color=color, date_added=datetime.now()
        )
        assert new_user, "Something went wrong with adding new user"

        # add the friend at session manager level
        callback = self.input_callbacks["add_friend"]
        self.loop.create_task(callback(new_user))

        # repoen any existing chats
        chats = self.view.find_chats(key)
        for chat in chats:
            self.view.layout.remove(chat)
            self.view.add_chat(chat_with=username)

        self.on_system_message_received(
            message=f"New friend {getattr(self.term, color)(username)} added!"
        )

    def remove_friend(self, friend: str) -> None:
        """Remove given key from friendslist."""
        friend_object = self.find_friend_by_id_or_username(friend)
        if not friend_object:
            raise Exception("Friend not in database.")
        if friend_object == self.myself or friend_object == self.system_user:
            raise Exception("Cannot remove system users.")
        friend_id = friend_object.id

        # close all chats with that user
        chats = self.view.find_chats(friend_id)
        for chat in chats:
            self.view.layout.remove(chat)

        self.db_manager.remove_friend(friend_id)
        self.on_system_message_received(message=f"Friend {friend_id} removed.")

    def get_friend_by_username(self, username: str) -> Optional[Friend]:
        """Return Friend object of a friend with given username."""
        friends = self.db_manager.get_all_friends()
        friends = list(
            filter(lambda x: x.username.lower() == username.lower(), friends)
        )

        return friends[0] if friends else None

    def get_friends(self) -> List:
        """Get list of friends from DB."""
        friends = self.db_manager.get_all_friends()

        return friends

    def print_pubkey_digest(self) -> None:
        """Print and copy user's own public key."""
        key = self.self_user_id
        pyperclip.copy(key)

        color = getattr(self.term, self.myself.color)

        self.on_system_message_received(
            message=f"Your public key digest, copied to clipboard: "
            f"{self.term.underline(color(key))}"
        )

    def on_new_message_received(
        self, message: Union[Message, str], user: Union[Friend, str]
    ) -> None:
        """Handle new message and add it to proper chat tiles."""
        if isinstance(user, str):
            id = user
        else:
            id = user.id
        friend = self.db_manager.get_friend(id)

        # unknown user
        if not friend:
            friend = Friend(id=id, username=id[:10], color="gray")
        self.view.add_message(friend, message)

    def show_friends(self) -> None:
        """Show friends (TODO: some real implementation)."""
        friends = self.get_friends()
        self.on_system_message_received(
            message=f"-----{self.term.bold_underline('Friends:')}-----"
        )
        for friend in friends:
            self.on_system_message_received(
                message=getattr(self.term, friend.color)(friend.username)
                + " - "
                + friend.id
            )

    def show_help(self) -> None:
        """Show help for slash commands."""
        full_message = f"-----{self.term.bold_underline('Commands:')}-----\n"
        full_message += (
            f"Press {self.term.purple('[escape]')} to enter layout mode.\n"
        )
        full_message += self.term.red(
            self.term.ljust("/comm", 8)
            + self.term.ljust(self.term.bold("REQUIRED,[optional]"), 16)
            + " description\n"
        )
        for name, command in self.slash_cmds.items():
            message = self.term.ljust(self.term.pink_underline("/" + name), 8)

            args = inspect.signature(command.callback).parameters.items()

            args_list = [
                x[0].upper()
                if x[1].default == inspect._empty  # type: ignore
                else "[" + x[0].lower() + "]"
                for x in args
            ]
            args_as_str = self.term.bold(",".join(args_list))
            message += self.term.ljust(args_as_str, 16) + " " * 4
            message += command.description
            full_message += message + "\n"

        self.on_system_message_received(message=full_message)

    def on_system_message_received(
        self, message: str, relevant_user: Union[Friend, str, None] = None
    ) -> None:
        """Handle new system message and add it to proper chat tiles."""
        message_model = Message(
            date=datetime.now(),
            body=message,
            from_user=self.system_user,
            to_user=self.myself,
        )

        if not relevant_user:
            assert self.system_user
            self.db_manager.save_message(
                body=message,
                date=datetime.now(),
                state=CansMessageState.DELIVERED,
                from_user=self.system_user.id,
                to_user=self.myself,
            )

            # TODO: what the heck is thaaaaaaat
            assert self.system_user
            if len(self.view.find_chats(self.system_user)) > 0:
                self.view.add_message(self.system_user, message=message)

            tile = self.view.layout.current_tile
            if isinstance(tile, ChatTile):
                if tile.chat_with != self.system_user:
                    self.view.add_message(tile.chat_with, message_model)
            elif len(self.view.find_chats(self.system_user)) == 0:
                self.view.add_chat(self.system_user)
                self.loop.create_task(self.view.render_all())

        else:
            self.on_new_message_received(message_model, relevant_user)

    def close_tile(self, target: Union[Tile, str, None] = None) -> None:
        """Close a tile."""
        if not target:
            targets = [self.view.layout.current_tile]
        elif isinstance(target, str):
            friend = self.get_friend_by_username(target)
            if not friend:
                return
            targets = self.view.find_chats(
                chats_with=friend.id  # type: ignore
            )
        else:
            targets = [target]
        try:
            # we don't want to close StartupTiles
            for target in targets:
                if target and not target == self.prompt_tile:
                    self.last_closed_tile.append(target)
                    self.view.layout.remove(target)
        except IndexError:
            return

        self.loop.create_task(self.view.layout.render_all())

    def reopen_tile(self) -> None:
        """Reopen last closed tile."""
        target = self.view.layout.current_tile
        if len(self.last_closed_tile) > 0:
            target = self.last_closed_tile.pop()

            # if were reopening chat it's safer to recreate it,
            # to have the entire message history
            if isinstance(target, ChatTile):
                self.view.add_chat(target.chat_with)
            else:
                self.view.layout.add(target)
        else:
            return

    def commands_allowed(self) -> bool:
        """Determine whether user can use commands.

        For example during startup, user should not be able to issue commands
        """
        if self.prompt_tile in self.view.layout.tiles:  # type: ignore
            return False
        else:
            return True

    def display_message(self, message: str, severity: str = "") -> None:
        """Display a message in a separate tile.

        Severity can be '' for normal and 'error' for error
        messages.
        """
        if severity == "error":
            title = self.term.red("Error message")
            color = "red_underline"
        else:
            title = "System message"
            color = "purple_bold"

        message_prompt = PromptTile(
            prompt_text=message,
            title=title,
            input_validation_function=None,
            border_color=color,
        )

        self.view.layout.add(message_prompt)
        self.loop.run_until_complete(self.view.render_all())

    def show_mnemonics(self, mnemonics: List[str]) -> None:
        """Show a generated list of one-time passwords.

        Those one-time password are later used in password recovery
        """
        message = (
            "Those are your one-time passwords, that you can use to "
            "recover your key if you forget your password. \n"
            + self.term.red_bold(
                "KEEP THEM SAFE AS THIS IS YOUR ONLY WAY TO RECOVER THE KEY!"
            )
            + "\n\n"
        )

        message += self.term.bold("\n".join(mnemonics))
        pyperclip.copy("\n".join(mnemonics))
        message += "\n\n" + self.term.green_underline("Copied to clipboard.")

        self.display_message(message)

    def complete_startup(self) -> None:
        """Close the startup tile and allow for normal mode of operation."""
        self.view.layout.remove(self.prompt_tile)  # type: ignore
        self.prompt_tile = None

        welcome_screen = PromptTile(
            prompt_text=f"Hello "
            f"{getattr(self.term, self.myself.color)(self.myself.username)}"
            f"! Use /chat [username] to start chatting, "
            f"type {self.term.purple('/frds')} to see your friendslist "
            f"or {self.term.purple('/help')} to see commands.",
            title="Welcome!",
            input_validation_function=None,
            close_on_input=True,
        )

        self.view.layout.add(welcome_screen)
        self.loop.run_until_complete(self.view.render_all())

    def blocking_prompt(
        self,
        prompt_config: Union[PasswordRecoveryState, StartupState, str],
        feedback: str = "",
    ) -> str:
        """Prompt user in blocking mode.

        Runs its own event loop. Look up UI.prompt_state_switches for
        reference.
        """
        self.set_prompt_tile(prompt_config)
        self.loop.run_until_complete(self.view.render_all())

        # set feedback if any
        assert self.prompt_tile
        if feedback:
            self.loop.run_until_complete(
                self.prompt_tile.consume_input(feedback, self.term)
            )

        user_input = self.loop.run_until_complete(self.prompt_queue.get())

        # reset input masking
        self.view.set_input_masking(False)

        return user_input

    async def create_queue(self) -> None:
        """Create a queue inside event loop."""
        self.prompt_queue: asyncio.Queue = asyncio.Queue()

    def _multistage_prompt(
        self,
        state_machine: StateMachine,
        feedback: str = "",
        isolate_state: bool = False,
    ) -> List[str]:
        """Inner function used for multi-stage inputs."""
        output = [""] * len(list(state_machine.type))

        while True:
            i = state_machine.state.value - 1

            # Generate prompt window
            self.set_prompt_tile(state=state_machine.state)

            # set feedback if any
            assert self.prompt_tile
            if feedback != "":
                self.loop.run_until_complete(
                    self.prompt_tile.consume_input(feedback, self.term)
                )

            self.loop.run_until_complete(self.view.render_all())

            # wait for user input
            user_input = self.loop.run_until_complete(self.prompt_queue.get())

            output[i] = user_input

            if isolate_state or state_machine.is_last:
                break
            state_machine.next()

        # reset input masking
        self.view.set_input_masking(False)

        return output

    def early_prompt_startup(
        self,
        state: StartupState = StartupState.PROMPT_USERNAME,
        feedback: str = "",
        isolate_state: bool = False,
    ) -> Config:
        """Prompt user before Client finishes init.

        Runs its own event loop. You can invoke it from any state you want.
        If state is specified, it will run ALL states after selected state,
        unless isolate_state is true.
        """
        state_machine = StateMachine(StartupState, state=state.value - 1)
        config = self._multistage_prompt(
            state_machine=state_machine,
            feedback=feedback,
            isolate_state=isolate_state,
        )

        return Config(*config)

    def set_prompt_tile(
        self, state: Union[PasswordRecoveryState, StartupState, str]
    ) -> None:
        """Create and set a vaild PromptTile as self.prompt_tile.

        Based on prompt state.
        """
        case = self.prompt_switches.get(state, "Invalid state")

        assert isinstance(case, PromptConfig)

        if not self.prompt_tile or self.prompt_tile.title != case.title:
            new_prompt = self.view.add_startup_tile(
                prompt_text=case.prompt,
                title=case.title,
                validation_function=case.validation,
            )
            if self.prompt_tile:
                self.view.layout.remove(self.prompt_tile)
            self.prompt_tile = new_prompt

        # set input masking
        self.view.set_input_masking(case.mask_input)

    async def _handle_user_input(self) -> None:
        """Handle user input asynchronously."""
        # set of focues commands, we use to not re render
        # everything on focus change
        focus_cmds = [
            self.view.layout.cmd_down,
            self.view.layout.cmd_up,
            self.view.layout.cmd_left,
            self.view.layout.cmd_right,
        ]

        # run forever
        while True:
            # get input from the input queue
            input_message = await (self.view.input_queue().get())

            # first part of input is input mode
            mode = input_message.mode
            # second part in input itself
            input_text = input_message.text

            cmd = None

            # handle graceful exit
            if mode == InputMode.EXIT:
                # Note that shutdown is an async coroutine and
                # must be awaited
                await self.input_callbacks["graceful_shutdown"]()

            # command mode
            elif mode == InputMode.COMMAND and self.commands_allowed():
                try:
                    if input_text[0] in self.slash_cmds:
                        cmd = self.slash_cmds[input_text[0]].callback
                        cmd(*input_text[1])

                    else:
                        self.on_system_message_received(
                            message=self.term.red(
                                f"Unknown command: /{input_text[0]}. "
                                f"Type {self.term.purple('/help')} "
                                f"to see available commands."
                            )
                        )
                except Exception as ex:
                    self.on_system_message_received(
                        message=self.term.red(
                            "Error executing slash command: " + ex.args[0]
                        )
                    )

            # layout mode, we're working inside the UI so
            # the user input isn't sent anywhere
            elif mode == InputMode.LAYOUT and input_text in self.cmds_layout:
                cmd = self.cmds_layout[input_text]
                if cmd:
                    # handle last closed tile reopening
                    if cmd == self.view.layout.add:
                        if len(self.last_closed_tile) > 0:
                            target = self.last_closed_tile.pop()
                            cmd(target)
                        else:
                            continue
                    else:
                        cmd()

                    if cmd in focus_cmds:
                        await self.view.layout.render_focus()
                    else:
                        await self.view.layout.render_all()
            # 'normal' input mode, we gather the input and then
            # issue a callback based on focused file type
            elif mode == InputMode.NORMAL:
                tile = self.view.layout.current_tile

                if tile and isinstance(tile, ChatTile) and input_text != "":
                    if isinstance(input_text, str):
                        input_text = input_text.strip()

                    if tile.is_prompting.locked() and isinstance(
                        input_text, str
                    ):
                        await tile.consume_input(input_text, self.term)
                    elif input_text == self.term.KEY_UP:
                        if tile.increment_offset():
                            await tile.render(self.term)
                    elif input_text == self.term.KEY_DOWN:
                        if tile.decrement_offset():
                            await tile.render(self.term)
                    elif tile.chat_with != self.system_user:
                        new_message = Message(
                            from_user=self.myself,
                            to_user=tile.chat_with,  # type: ignore
                            body=input_text,
                            date=datetime.now(),
                            state=CansMessageState.NOT_DELIVERED.value,
                        )  # type: ignore
                        tile.reset_offset()
                        # pass the message to the client core
                        await self.input_callbacks["upstream_message"](
                            new_message
                        )

                # Prompt Tile handling
                elif isinstance(tile, PromptTile) and isinstance(
                    input_text, str
                ):
                    input_text = input_text.strip()
                    feedback = ""
                    # if validfation function is set, first validate input
                    if tile.input_validation:
                        validation = tile.input_validation(input_text)
                        if not validation:
                            feedback = (
                                "Input validation failed. "
                                "Try with different input."
                            )
                            await tile.consume_input(feedback, self.term)
                            continue

                    # prompt tile handling
                    if tile == self.prompt_tile:

                        await self.prompt_queue.put(input_text)
                        if feedback != "":
                            await self.prompt_tile.consume_input(
                                feedback, self.term
                            )
                        await self.prompt_tile.render(self.term)

                    else:
                        if tile.close_on_input:
                            self.close_tile(target=tile)
                            await self.view.layout.render_all()
                        else:
                            await tile.consume_input(
                                f"Use {self.term.purple_bold('/chat')} "
                                "to chat, don't waste your time here",
                                self.term,
                            )
