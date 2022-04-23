"""
View class for user interface.

Divides terminal into independent windows
"""
import asyncio
import concurrent
import hashlib
import signal
from datetime import datetime
from threading import Event
from typing import Any, Callable, List, Union

from blessed import Terminal

from ..models import MessageModel, UserModel
from .tiles import ChatTile, HeaderTile, InputTile, Tile
from .tiling_managers import MonadTallLayout


class View:
    """
    A class representing current View of the application.

    Contains a list of active Tiles and controls their layout
    """

    def __init__(
        self,
        term: Terminal,
        loop: Union[asyncio.BaseEventLoop, asyncio.AbstractEventLoop],
    ) -> None:
        """Instantiate a view."""
        self.term = Terminal()
        self.loop = loop

        self.on_resize_event = Event()

        # set identity
        self.myself = UserModel(username="Alice", id="123", color="green")

        # create a header tile -- always on top
        header = HeaderTile(
            name="Title bar",
            title=term.red_underline("cans") + " secure messenger",
            right_title=term.green_underline("α") + "-version",
            width=term.width,
            height=2,
            x=0,
            y=0,
            margins="d",
        )

        footer = InputTile(
            name="Input",
            width=term.width,
            height=1,
            x=0,
            y=self.term.height - 1,
            margins="",
        )

        self.header = header
        self.footer = footer

        # run input in another thread
        # yes there really has to be so many of them noqa's :)
        loop.create_task(  # noqa: FKA01
            self.run_in_thread(  # noqa: FKA01
                self.footer.input,  # noqa: FKA01
                self.term,  # noqa: FKA01
                self.loop,  # noqa: FKA01
                self.on_resize_event,  # noqa: FKA01
            )  # noqa: FKA01
        )  # noqa: FKA01

        # set up layout manager
        self.layout = MonadTallLayout(
            width=self.term.width,
            height=self.term.height - header.height - footer.height,
            x=0,
            y=header.height,
            term=self.term,
            use_margins=True,
        )

        # add chat tile to the layout
        # self.layout.add(chat)

        # add a signal handler for resizing
        loop.add_signal_handler(signal.SIGWINCH, self.on_resize)

        # render the screen
        loop.run_until_complete(self.render_all())

    async def render_all(self) -> None:
        """Render header, footer and layout."""
        await (self.layout.render_all())
        await (self.header.render(self.term))
        await (self.footer.render(self.term))

    async def run_in_thread(self, task: Callable, *args: Any) -> None:
        """Run funntion in another thread."""
        # Run in a custom thread pool:
        pool = concurrent.futures.ThreadPoolExecutor()
        await self.loop.run_in_executor(pool, task, *args)  # noqa: FKA01

    def on_resize(self, *args: str) -> None:
        """React to screen resize."""
        self.layout.screen_rect_change(
            width=self.term.width,
            height=self.term.height - self.header.height - self.footer.height,
            x=0,
            y=self.header.height,
        )
        self.header.width = self.term.width

        self.loop.create_task(self.layout.render_all())
        self.loop.create_task(self.header.render(self.term))
        self.on_resize_event.set()

    def add_chat(self, chat_with: UserModel) -> None:
        """Add a chat tile with a given user."""
        # get the color attribute from terminal
        color = getattr(self.term, chat_with.color)

        chat = ChatTile(
            name="Chat",
            chat_with=chat_with,
            title=f"Chat with {color(chat_with.username)}",
        )
        self.layout.add(chat)
        self.loop.create_task(self.layout.render_all())

    def find_chats(self, chats_with: UserModel) -> List[Tile]:
        """Find chat tiles with a given user."""
        found_tiles = []

        for tile in self.layout.tiles:
            # fuck mypy dude im not gonna fight with inheritance
            if (
                type(tile)
            ) == ChatTile and tile.chat_with == chats_with:  # type: ignore
                found_tiles.append(tile)

        return found_tiles

    def add_message(self, chat_with: UserModel, message: MessageModel) -> None:
        """Add a message to buffers of chat tiles with given user."""
        chats = self.find_chats(chat_with)
        if chats is not None:
            for chat in chats:
                self.loop.create_task(
                    chat.add_message_to_buffer(message)  # type: ignore
                )  # type: ignore

    def input_queue(self) -> asyncio.Queue:
        """Return user input queue."""
        return self.footer.input_queue


if __name__ == "__main__":
    term = Terminal()
    loop = asyncio.get_event_loop()

    view = View(term, loop)

    eve = UserModel(
        username="Eve",
        id=hashlib.md5("ee".encode("utf-8")).hexdigest(),
        color="blue",
    )

    bob = UserModel(
        username="Bob",
        id=hashlib.md5("aa".encode("utf-8")).hexdigest(),
        color="red",
    )
    view.add_chat(bob)

    # create chat tile with eve
    view.add_chat(eve)
    view.add_chat(eve)
    view.add_chat(eve)
    view.add_chat(eve)

    chats_with_bob = view.find_chats(bob)
    chats_with_eve = view.find_chats(eve)

    messages_with_bob = [
        MessageModel(
            from_user=view.myself,
            to_user=bob,
            body="don't know... let's try:",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            to_user=view.myself,
            from_user=bob,
            body=f"Okay that's { term.lightgreen_bold('cool') }, "
            "but do we have markdown support?",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=view.myself,
            to_user=bob,
            body=term.blue_underline(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            ),
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=view.myself,
            to_user=bob,
            body="Observe",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=bob,
            to_user=view.myself,
            body="No way dude",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=view.myself,
            to_user=bob,
            body="You know we can post links here?",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=bob,
            to_user=view.myself,
            body="What do you want",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=view.myself,
            to_user=bob,
            body="Hi",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=bob,
            to_user=view.myself,
            body="Hello",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
    ]

    messages_with_eve = [
        MessageModel(
            from_user=view.myself,
            to_user=eve,
            body="don't know... let's try:",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=eve,
            to_user=view.myself,
            body="hello there",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
        MessageModel(
            from_user=view.myself,
            to_user=eve,
            body="heya",
            date=datetime(
                year=2022, month=3, day=21, hour=11, minute=36, second=15
            ),
        ),
    ]

    messages_with_bob.reverse()
    for message in messages_with_bob:
        view.add_message(bob, message)

    for message in messages_with_eve:
        view.add_message(eve, message)

    loop.run_forever()
