"""CANS application UI."""
import asyncio
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Union

from blessed import Terminal

from ..models import MessageModel, UserModel
from .tiles import ChatTile, Tile
from .view import View


class UserInterface:
    """CANS application UI."""

    def __init__(
        self, loop: Union[asyncio.BaseEventLoop, asyncio.AbstractEventLoop]
    ) -> None:
        """Instantiate a UI."""
        # Set terminal and event loop
        self.term = Terminal()
        self.loop = loop

        # Instantiate a view
        self.view = View(self.term, self.loop)

        # start user input handler
        self.loop.create_task(self._handle_user_input())

        # set identity
        self.myself = UserModel(username="Alice", id="123", color="green")
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

            # ctrl+d
            chr(4):     self.view.layout.remove,
        }  # fmt: skip
        """Mapping for layout changing commands"""

    def on_new_message_received_str(
        self, message: str, user: UserModel
    ) -> None:
        """Handle new message and add it to proper chat tiles."""
        new_message = MessageModel(
            from_user=user,
            to_user=self.myself,
            body=message,
            date=datetime.now(),
        )
        self.view.add_message(user, new_message)

    def on_new_message_received(
        self, message: MessageModel, user: UserModel
    ) -> None:
        """Handle new message and add it to proper chat tiles."""
        self.view.add_message(user, message)

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
            inp_tuple = await (self.view.input_queue().get())

            # first part of input is input mode
            mode = inp_tuple[0]
            # second part in input itself
            inp = inp_tuple[1]

            cmd = None

            # layout mode, we're working inside the UI so
            # the user input isn't sent anywhere
            if mode == "layout" and inp in self.cmds_layout:
                cmd = self.cmds_layout[inp]
                if cmd:
                    # handle tile removal
                    if cmd == self.view.layout.remove:
                        target = self.view.layout.focused
                        try:
                            cmd(self.view.layout.tiles[target])
                        except IndexError:
                            pass
                    else:
                        cmd()
                    if cmd in focus_cmds:
                        await self.view.layout.render_focus()
                    else:
                        await self.view.layout.render_all()
            # 'normal' input mode, we gather the input and then
            # issue a callback based on focused file type
            elif mode == "":
                tile = self.view.layout.current_tile
                tile_type = type(tile)

                if tile and tile_type == ChatTile:
                    new_message = MessageModel(
                        from_user=self.myself,
                        to_user=tile.chat_with,  # type: ignore
                        body=inp,
                        date=datetime.now(),
                    )  # type: ignore
                    self.view.add_message(
                        tile.chat_with, new_message  # type: ignore
                    )  # type: ignore
                    # some callback to client would be needed
                    # TODO: add callback for client

                elif tile and tile_type == Tile:
                    tile.consume_input(inp, self.term)
                    pass

    def say_hello(self) -> None:
        """Says f*cking hello."""
        print("hello 2")
