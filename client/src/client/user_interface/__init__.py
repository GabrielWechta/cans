"""CANS application UI."""
import asyncio
import os
from collections import namedtuple
from datetime import datetime
from random import choice
from typing import Any, Callable, List, Mapping, Optional, Union

from blessed import Terminal
from blessed.formatters import FormattingString

from ..database_manager_client import DatabaseManager
from ..models import CansMessageState, Friend, Message
from .input import InputMode
from .state_machines import StartupState, StateMachine
from .tiles import ChatTile, PromptTile, Tile
from .view import View

InputState = namedtuple("InputState", "callback_name title prompt validation")


class UserInterface:
    """CANS application UI."""

    def __init__(
        self,
        loop: Union[asyncio.BaseEventLoop, asyncio.AbstractEventLoop],
        input_callbacks: Mapping[str, Callable],
        identity: Friend,
        db_manager: DatabaseManager,
        first_startup: bool,
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
            identity=identity,
            db_manager=self.db_manager,
        )

        # start user input handler
        self.loop.create_task(self._handle_user_input())

        # set identity
        self.myself = identity
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

        self.slash_cmds: Mapping[str, Callable[..., Any]] = {
            "chat": self.view.add_chat,
            "swap": self.view.swap_chat,
            "close": self.close_tile,
            "help": self.show_help,
            "friends": self.show_friends,
            "add": self.add_friend,
            "remove": self.remove_friend,
        }
        """Mapping for slash commands"""

        self.system_user = self.db_manager.add_friend(
            username="System",
            id="system",
            color="orange_underline",
            date_added=datetime.now(),
        )
        """System user for system commands"""

        self.startup_states_switches = {
            StartupState.PROMPT_USERNAME: InputState(
                callback_name="set_identity_username",
                title=" 1 - Set username",
                prompt=f"Welcome to {self.term.red_bold_underline('cans')}! "
                "Please input your username, it can be changed later. "
                "Username cannot contain trailing/leading whitespaces and "
                "cannot be empty.",
                validation=self.validate_username,
            ),
            StartupState.PROMPT_COLOR: InputState(
                callback_name="set_identity_color",
                title=" 2 - Set color",
                prompt="Please input the color you want to "
                "use for your username, "
                "it can be changed later.",
                validation=self.validate_color,
            ),
            StartupState.PROMPT_PASSWORD: InputState(
                callback_name="set_password",
                title=" [3] - [Optional] Set password",
                prompt="If you want to have additional protection, input a "
                "password for your account. Password cannot contain any "
                "whitespace characters and if provided it should be at "
                "least 6 characters long.",
                validation=self.validate_password,
            ),
        }
        """Startup states in from (callback_name, tile, prompt, validation)"""

        self.last_closed_tile: List[Tile] = []

        # launch StartupTile
        self.first_startup = first_startup

        self.startup_tile: Optional[PromptTile] = None
        if not self.first_startup:
            self.startup_tile = self.view.add_startup_tile(
                prompt_text="Please enter password. Input '/'"
                " to enter password recovery mode.",
                title="Startup",
                validation_function=self.validate_password,
            )
        else:
            self.startup_tile = None
            self.first_startup_prompt(
                state=StateMachine(StartupState, state=0).state
            )

        self.loop.create_task(self.view.render_all())

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
        if password == "":
            return True
        password_without_whitespace = "".join(password.split())
        return password == password_without_whitespace and len(password) >= 6

    def validate_username(self, username: str) -> bool:
        """Validate if given username is valid."""
        if username == "":
            return False
        username_stripped = username.strip()
        return username == username_stripped

    def add_friend(self, username: str, key: str, color: str = "") -> None:
        """Add given key to friendslist."""
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
            ]
            color = choice(colors)

        assert self.validate_color(color), "Color unknown"
        # TODO: make it so it has a different message when
        # adding an already used key
        new_user = self.db_manager.add_friend(
            username=username, id=key, color=color, date_added=datetime.now()
        )
        assert new_user, "Something went wrong with adding new user"
        self.on_system_message_received(
            message=f"New friend {getattr(self.term, color)(username)} added!"
        )

    def remove_friend(self, key: str) -> None:
        """Remove given key from friendslist."""
        # TODO: remove from db
        pass

    def get_friends(self) -> List:
        """Get list of friends from DB."""
        friends = self.db_manager.get_all_friends()

        return friends

    def on_new_message_received(
        self, message: Union[Message, str], user: Union[Friend, str]
    ) -> None:
        """Handle new message and add it to proper chat tiles."""
        self.view.add_message(user, message)

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
        self.on_system_message_received(
            message=f"-----{self.term.bold_underline('Commands:')}-----"
        )
        for command in self.slash_cmds.keys():
            self.on_system_message_received(
                message=self.term.pink_underline("/" + command)
            )

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

    def close_tile(self) -> None:
        """Close focused tile."""
        target = self.view.layout.current_tile
        try:
            # we don't want to close StartupTiles
            if target and not target == self.startup_tile:
                self.last_closed_tile.append(target)
                self.view.layout.remove(target)
        except IndexError:
            return

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
        if self.startup_tile in self.view.layout.tiles:  # type: ignore
            return False
        else:
            return True

    async def complete_startup(self) -> None:
        """Close the startup tile and allow for normal mode of operation."""
        self.view.layout.remove(self.startup_tile)  # type: ignore
        self.startup_tile = None

        welcome_screen = PromptTile(
            prompt_text=f"Hello "
            f"{getattr(self.term, self.myself.color)(self.myself.username)}"
            f"! Use /chat [username] to start chatting, "
            f"or type /friends to see your friendslist.",
            title="Welcome!",
            input_validation_function=None,
        )

        self.view.layout.add(welcome_screen)
        await self.view.render_all()

    def first_startup_prompt(self, state: StartupState) -> str:
        """
        Set valid prompt tile as startup tile, based on startup state.

        Returns callback_name of callback to call.
        """
        case = self.startup_states_switches.get(state, "Invalid state")

        assert isinstance(case, InputState)

        if (
            not self.startup_tile
            or self.startup_tile.title != "Startup" + case[1]
        ):
            new_startup = self.view.add_startup_tile(
                prompt_text=case.prompt,
                title="Startup" + case.title,
                validation_function=case.validation,
            )
            if self.startup_tile:
                self.view.layout.remove(self.startup_tile)
            self.startup_tile = new_startup

        return case[0]

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

        if self.first_startup:
            first_startup_sm = StateMachine(StartupState, state=0)

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
                print(self.term.exit_fullscreen)
                # TODO: add callback to client to
                # gracefully close the application
                os._exit(0)

            # command mode
            elif mode == InputMode.COMMAND and self.commands_allowed():
                try:
                    if input_text[0] in self.slash_cmds:
                        cmd = self.slash_cmds[input_text[0]]
                        cmd(*input_text[1])

                        await self.view.layout.render_all()
                    else:
                        self.on_system_message_received(
                            message=self.term.red(
                                f"Unknown command: /{input_text[0]}"
                            )
                        )
                except Exception as ex:
                    self.on_system_message_received(
                        message=self.term.red(
                            "Error parsing slash command: " + ex.args[0]
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
                    # handle buffer scroll
                    if input_text == self.term.KEY_UP:
                        tile.increment_offset()
                        await tile.render(self.term)
                    elif input_text == self.term.KEY_DOWN:
                        tile.decrement_offset()
                        await tile.render(self.term)
                    elif tile.chat_with != self.system_user:
                        new_message = Message(
                            from_user=self.myself,
                            to_user=tile.chat_with,  # type: ignore
                            body=input_text,
                            date=datetime.now(),
                            state=CansMessageState.DELIVERED,
                        )  # type: ignore
                        tile.reset_offset()
                        self.view.add_message(
                            tile.chat_with, new_message  # type: ignore
                        )  # type: ignore
                        # TODO: do it on client level
                        self.db_manager.save_message(
                            body=input_text,
                            date=datetime.now(),
                            state=CansMessageState.DELIVERED,
                            from_user=self.myself.id,
                            to_user=tile.chat_with.id,
                        )
                        # pass the message to the client core
                        await self.input_callbacks["upstream_message"](
                            new_message
                        )

                # Prompt Tile handling
                elif isinstance(tile, PromptTile) and isinstance(
                    input_text, str
                ):
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

                    # startup handling
                    if tile == self.startup_tile:

                        # First startup handling
                        if self.first_startup:
                            callback = self.first_startup_prompt(
                                first_startup_sm.state
                            )
                            feedback = self.input_callbacks[callback](
                                input_text
                            )
                            if feedback == "":
                                if first_startup_sm.is_last:
                                    await self.complete_startup()
                                else:
                                    self.first_startup_prompt(
                                        first_startup_sm.next()  # type: ignore
                                    )
                                await self.view.render_all()
                                continue
                            await self.startup_tile.consume_input(
                                feedback, self.term
                            )
                        # Normal startup handling
                        else:
                            # TODO: add calback to password check function
                            # feedback = callback(password = input_text)
                            # TODO: add password recovery mode
                            feedback = self.input_callbacks["decrypt_key"](
                                input_text
                            )
                            if feedback == "":
                                await self.complete_startup()
                                await self.view.render_all()
                                continue
                            await self.startup_tile.consume_input(
                                feedback, self.term
                            )
                    else:
                        await tile.consume_input(
                            f"Use {self.term.purple_bold('/chat')} to chat, "
                            "don't waste your time here",
                            self.term,
                        )
