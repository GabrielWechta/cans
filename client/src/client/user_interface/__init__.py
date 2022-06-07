"""CANS application UI."""
import asyncio
import os
from datetime import datetime
from random import choice
from typing import Any, Callable, List, Mapping, Optional, Union

from blessed import Terminal

from ..database_manager_client import DatabaseManager
from ..models import CansMessageState, Friend, Message
from .input import InputMode
from .tiles import ChatTile, PromptTile, Tile
from .view import View


class UserInterface:
    """CANS application UI."""

    def __init__(
        self,
        loop: Union[asyncio.BaseEventLoop, asyncio.AbstractEventLoop],
        upstream_callback: Callable,
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

        # Store the client callback
        self.upstream_callback = upstream_callback

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

        self.last_closed_tile: List[Tile] = []

        # launch StartupTile
        self.startup_tile = self.view.add_startup_tile(first_startup)

        self.loop.create_task(self.view.render_all())

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
        # TODO: some better sanitizing
        assert getattr(self.term, color), "Color unknown"
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

            # if were reading chat it's safer to recreate it,
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
        if self.startup_tile in self.view.layout.tiles:
            return False
        else:
            return True

    async def complete_startup(self) -> None:
        """Close the startup tile and allow for normal mode of operation."""
        self.view.layout.remove(self.startup_tile)

        welcome_screen = PromptTile(
            prompt_text=f"Hello "
            f"{getattr(self.term, self.myself.color)(self.myself.username)}"
            f"! Use /chat [username] to start chatting, "
            f"or type /friends to see your friendslist.",
            title="Welcome!",
        )

        self.view.layout.add(welcome_screen)
        await self.view.render_all()

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
                print(self.term.exit_fullscreen)
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

                if tile and isinstance(tile, ChatTile):
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
                        await self.upstream_callback(new_message)
                elif tile == self.startup_tile and isinstance(input_text, str):
                    # TODO: add calback to password check function
                    # feedback = callback(password = input_text)
                    # TODO: add password recovery mode
                    feedback = "Error"
                    if feedback == "" or input_text == "test":
                        await self.complete_startup()
                        continue
                    await tile.consume_input(feedback, self.term)
                elif isinstance(tile, PromptTile) and isinstance(
                    input_text, str
                ):
                    await tile.consume_input(
                        f"Use {self.term.purple_bold('/chat')} to chat, "
                        "don't waste your time here",
                        self.term,
                    )
