"""CANS application UI."""
import asyncio
from typing import Union

from blessed import Terminal

from .view import View


class UserInterface:
    """CANS application UI."""

    term: Terminal
    """Blessed Terminal object used to work with system's Terminal Emulator"""

    def __init__(
        self, loop: Union[asyncio.BaseEventLoop, asyncio.AbstractEventLoop]
    ) -> None:
        """Instantiate a UI."""
        # Set terminal and event loop
        self.term = Terminal()
        self.loop = loop

        # Instantiate a view
        self.view = View(self.term, self.loop)

    def on_new_message_received(self) -> None:
        """Handle new message and add it to proper chat tiles."""
        pass

    def say_hello(self) -> None:
        """Says fucking hello."""
        print("hello 2")
