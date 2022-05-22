"""
View class for user interface.

Divides terminal into independent windows
"""
import asyncio
import concurrent
import logging
import signal
from datetime import datetime
from threading import Event
from typing import Any, Callable, List, Mapping, Union

from blessed import Terminal

from ..database_manager_client import DatabaseManager
from ..models import Friend, Message
from .tiles import ChatTile, HeaderTile, InputTile
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
        identity: Friend,
        db_manager: DatabaseManager,
    ) -> None:
        """Instantiate a view."""
        self.term = Terminal()
        self.loop = loop
        self.db_manager = db_manager

        self.log = logging.getLogger("cans-logger")

        self.on_resize_event = Event()

        # set identity
        self.myself = identity

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

    def get_message_history(self, user: Friend) -> List[Message]:
        """Get message history for a given user."""
        messages = self.db_manager.get_message_history_with_friend(user.id)

        if messages:
            messages.reverse()
            return messages
        else:
            return []

    def get_friends(self) -> Mapping[str, Friend]:
        """Get list of friends from DB as username:Friend dict."""
        friends = self.db_manager.get_all_friends()

        friends_dict = {}
        for friend in friends:
            friends_dict[friend.username.lower()] = friend

        return friends_dict

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

    def add_chat(self, chat_with: Union[Friend, str]) -> None:
        """Add a chat tile with a given user."""
        # TODO: get it from DB
        if isinstance(chat_with, str):
            chat_with = chat_with.lower()
            friends = self.get_friends()
            if chat_with in friends:
                chat_with = friends[chat_with]
            else:
                raise Exception(f"Unknown user: {chat_with}")

        history = self.get_message_history(chat_with)

        # get the color attribute from terminal
        color = getattr(self.term, chat_with.color)

        chat = ChatTile(
            name="Chat",
            chat_with=chat_with,
            title=f"Chat with {color(chat_with.username)}",
            identity=self.myself,
            buffer=history,
        )
        self.layout.add(chat)
        # self.loop.create_task(self.layout.render_all())

    def swap_chat(self, chat_with: Union[Friend, str]) -> None:
        """Add swap current tile with a new chat with given user."""
        tile_before = self.layout.current_tile

        # TODO: get it from DB
        if isinstance(chat_with, str):
            friends = self.get_friends()
            if chat_with in friends:
                chat_with = friends[chat_with]
            else:
                raise Exception(f"Unknown user: {chat_with}")

        # Already chatting with that user, do nothing
        if isinstance(tile_before, ChatTile):
            if chat_with.id == tile_before.chat_with.id:
                return

        # add new chat
        self.add_chat(chat_with)
        tile_after = self.layout.current_tile

        assert isinstance(tile_before, ChatTile) and isinstance(
            tile_after, ChatTile
        )

        # swap the tiles
        self.layout.cmd_swap(tile_after, tile_before)

        # delete the old tile
        self.layout.remove(tile_before)

    def find_chats(self, chats_with: Union[Friend, str]) -> List[ChatTile]:
        """Find chat tiles with a given user or user id."""
        found_tiles = []

        # if Friend is provided
        if isinstance(chats_with, Friend):
            user_id = chats_with.id
        # if string is provided
        else:
            user_id = chats_with

        for tile in self.layout.tiles:
            # f*ck mypy dude im not gonna fight with inheritance
            if isinstance(tile, ChatTile) and tile.chat_with.id == user_id:
                found_tiles.append(tile)

        return found_tiles

    def add_message(
        self,
        chat_with: Union[Friend, str],
        message: Union[Message, str],
    ) -> None:
        """Add a message to buffers of chat tiles with given user of id."""
        chats = self.find_chats(chat_with)
        if len(chats) > 0:
            # if we're provided with a Message, just use it
            if isinstance(message, Message):
                new_message = message
            # else we only have payload, so we have to construct it
            else:
                new_message = Message(
                    from_user=chats[0].chat_with,  # type: ignore
                    to_user=self.myself,
                    body=message,  # type: ignore
                    date=datetime.now(),
                )

            for chat in chats:
                self.loop.create_task(
                    chat.add_message_to_buffer(new_message)  # type: ignore
                )  # type: ignore
        else:
            self.log.error(
                # it's always either a dataclass or string, should print nicely
                f"Tried adding message {message}"
                + f" to a non-existing chat with {chat_with}"
            )

    def input_queue(self) -> asyncio.Queue:
        """Return user input queue."""
        return self.footer.input_queue


if __name__ == "__main__":
    term = Terminal()
    loop = asyncio.get_event_loop()
