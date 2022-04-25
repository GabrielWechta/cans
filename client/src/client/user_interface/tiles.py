"""Tile classes for emulating independent I/O widgets of specified size."""

import math
from asyncio import BaseEventLoop, Queue, run_coroutine_threadsafe
from datetime import datetime
from threading import Event
from typing import Any, List, Tuple

from blessed import Terminal, keyboard

from ..models import MessageModel, UserModel


class Tile:
    """Tile class for emulating an independent I/O widget of specified size."""

    margin = {
        "l": "|",
        "r": "|",
        "u": "—",
        "d": "—",
    }

    def __init__(
        self,
        name: str,
        width: int = 0,
        height: int = 0,
        x: int = 0,
        y: int = 0,
        margins: str = "",
        title: str = "",
    ) -> None:
        """Instantiate a tile."""
        self.name = name

        self.x = x
        self.y = y

        self._margins = margins
        self._height = 0
        self._width = 0
        self.width = width
        self.height = height
        self.focused = False
        self.title = title
        self.real_size()
        self.body = ""

    @property
    def margins(self) -> str:
        """Define margins of tile."""
        return self._margins

    @margins.setter
    def margins(self, margins: str) -> None:
        self._margins = margins
        self.real_size()

    @property
    def width(self) -> int:
        """Return width of a Tile (rendering width)."""
        return self._width

    @width.setter
    def width(self, width: int) -> None:
        """Set width of a Tile (rendering width)."""
        self._width = width
        self.real_size()

    @property
    def height(self) -> int:
        """Return height of a Tile (rendering height)."""
        return self._height

    @height.setter
    def height(self, height: int) -> None:
        """Set height of a Tile (rendering height)."""
        self._height = height
        self.real_size()

    async def consume_input(self, inp: str, t: Terminal) -> None:
        """Consume some input in some way."""
        self.body = inp
        await self.render(t)

    def real_size(self) -> None:
        """Calculate real size, excluding margins etc."""
        width = (
            self._width - int("l" in self.margins) - int("r" in self.margins)
        )
        height = (
            self._height - int("u" in self.margins) - int("d" in self.margins)
        ) - 1  # for titlebar

        self.real_width = width
        self.real_height = height

    def truncate(self, text: str, t: Terminal) -> str:
        """Truncate text to fit into the rendering box."""
        out = text
        if t.length(text) > self.real_width:
            out = t.truncate(text, self.real_width - 1)
            out += t.on_red(">")
        return out

    async def render(self, t: Terminal) -> None:
        """Render the Tile."""
        # render title bar
        await self.render_titlebar(t)

        # for now just fill the Tile with some symbol
        for y in range(0 + 1, (self.real_height + 1)):  # +1 for title
            with t.hidden_cursor(), t.location(
                (self.x + int("l" in self.margins)),
                (self.y + int("u" in self.margins) + y),
            ):
                out = (self.real_width) * " "
                if not self.focused:
                    print(out, end="")
                else:
                    print(out, end="")
                    # print(t.red(out), end="")
        with t.hidden_cursor(), t.location(
            (self.x + int("l" in self.margins)),
            (self.y + int("u" in self.margins) + 1),
        ):
            print(self.truncate(str(self.body), t))
        # print margins
        await self.render_margins(t)

    async def render_titlebar(self, t: Terminal) -> None:
        """Render title bar of a Tile."""
        with t.hidden_cursor(), t.location(
            self.x + int("l" in self.margins),
            self.y + int("u" in self.margins),
        ):
            title = self.title if self.title != "" else self.name
            out = self.truncate(title, t)
            out = t.ljust(out, self.real_width)
            print(out, end="")

    async def render_margins(self, t: Terminal) -> None:
        """Render margins of a tile."""
        attr = "red" if self.focused else "normal"

        color = getattr(t, attr)
        if "l" in self._margins:
            for y in range(0, (self._height)):
                with t.hidden_cursor(), t.location((self.x), (self.y + y)):
                    out = self.margin["l"]
                    print(color + out, end="")
        if "r" in self._margins:
            for y in range(0, (self._height)):
                with t.hidden_cursor(), t.location(
                    (self.x + self._width - 1), (self.y + y)
                ):
                    out = self.margin["r"]
                    print(color + (out), end="")
        if "d" in self._margins:
            with t.hidden_cursor(), t.location(
                (self.x), (self.y + self._height - 1)
            ):
                out = (self._width) * self.margin["d"]
                print(color + (out), end="")
        if "u" in self._margins:
            with t.hidden_cursor(), t.location((self.x), (self.y)):
                out = (self._width) * self.margin["u"]
                print(color + (out), end="")

    async def render_focus(self, t: Terminal) -> None:
        """Render only the focus indicator."""
        await self.render_margins(t)

    def info(self) -> str:
        """Return Tile info."""
        return f"""
----------------
Tile            {self.name}
x:              {self.x}
y:              {self.y}
width:          {self.width}
height:         {self.height}
----------------
        """


class HeaderTile(Tile):
    """Header Tile."""

    def __init__(
        self, right_title: str = "", *args: Any, **kwargs: Any
    ) -> None:
        """Init input Tile."""
        self.right_title = right_title
        Tile.__init__(self, *args, **kwargs)

    async def render_titlebar(self, t: Terminal) -> None:
        """Render title bar of a HeaderTile."""
        title_left = self.title
        title_right = t.rjust(self.right_title, t.width - t.length(title_left))

        self.title = title_left + title_right
        await Tile.render_titlebar(self, t)
        self.title = title_left

    async def render(self, t: Terminal) -> None:
        """Render the Tile."""
        await self.render_margins(t)
        await self.render_titlebar(t)


class InputTile(Tile):
    """Input Tile."""

    def __init__(self, prompt: str = "> ", *args: Any, **kwargs: Any) -> None:
        """Init input Tile."""
        self.prompt = prompt
        Tile.__init__(self, *args, **kwargs)
        self.input_queue: Queue = Queue()
        self.prompt_position = math.floor(self.real_height / 2)

        self.mode = ""

    def real_size(self) -> None:
        """Calculate real size, excluding margins etc."""
        width = (
            self._width - int("l" in self.margins) - int("r" in self.margins)
        ) - Terminal().length(self.prompt)
        height = (
            self._height - int("u" in self.margins) - int("d" in self.margins)
        ) - 1  # for titlebar

        self.real_width = width
        self.real_height = height

    async def on_resize(self, t: Terminal) -> None:
        """
        React to terminal size change.

        InputTile runs in it's own thread, so it has to have this signal
        defined.
        """
        self.width = t.width

        # keep height as it was
        self.height = self.height
        self.x = self.x

        self.prompt_position = math.floor(self.real_height / 2)

        # it's always on the botton of the screen
        self.y = t.height - self.height

        await self.clear_input(t)

        await self.render(t)

    def input(
        self, term: Terminal, loop: BaseEventLoop, on_resize_event: Event
    ) -> None:
        """
        Input function, REALLY BAD.

        TODO: think about better implementation.
        """
        inp = ""
        prompt_location = self.prompt_location()
        print(term.move_xy(prompt_location[0], prompt_location[1]), end="")
        # basically run forever
        while True:
            # set cursor position
            with term.raw():
                prompt_location = self.prompt_location()
                x_pos = prompt_location[0] + term.length(inp)
                y_pos = prompt_location[1]

                # paste handling, use the first character to check
                # command type and add rest as additional input
                val = term.inkey()

                if self.mode == "" and self.input_filter(val):
                    x_pos += 1

                next = term.inkey(
                    timeout=0.010
                )  # this is basically polling rate
                add_input = ""
                while next and self.input_filter(next):
                    add_input += next
                    next = term.inkey(timeout=0.010)

                print(
                    term.move_xy(x_pos + term.length(add_input), y_pos), end=""
                )
                # we have to somehow now that terminal
                # has resized from this thread
                # as the signals only work in main,
                if on_resize_event.is_set():
                    on_resize_event.clear()
                    run_coroutine_threadsafe(self.on_resize(term), loop)

                # workaround to have a working ctrl+c in raw mode
                # and with threads
                if val == chr(3):
                    # os._exit(1)
                    # break the loop to leave raw environment
                    # send a message that we want to quit
                    run_coroutine_threadsafe(
                        self.input_queue.put(("exit", "")), loop
                    )
                    break
                # if normal mode
                if self.mode == "":
                    if val.code == term.KEY_ESCAPE:
                        self.mode = "layout"
                    else:
                        # if enter was pressed, return input
                        if val.code == term.KEY_ENTER and inp != "":
                            run_coroutine_threadsafe(
                                self.input_queue.put((self.mode, inp)), loop
                            )
                            print(
                                term.move_xy(
                                    prompt_location[0], prompt_location[1]
                                ),
                                end="",
                            )
                            inp = ""
                        elif (
                            val.code == term.KEY_BACKSPACE
                            or val.code == term.KEY_DELETE
                        ):
                            inp = inp[:-1]
                            print(
                                term.move_xy(
                                    prompt_location[0] + term.length(inp),
                                    prompt_location[1],
                                ),
                                end="",
                            )
                        elif self.input_filter(val):
                            inp += val + add_input
                        run_coroutine_threadsafe(
                            self.display_prompt(inp, term), loop
                        )
                # if layout mode
                if self.mode == "layout":
                    if val.code == term.KEY_ENTER:
                        self.mode = ""
                    else:
                        if self.input_filter(val) or not val.code:
                            run_coroutine_threadsafe(
                                self.input_queue.put((self.mode, val)), loop
                            )
                        else:
                            run_coroutine_threadsafe(
                                self.input_queue.put((self.mode, val.code)),
                                loop,
                            )
        # print(term.exit_fullscreen, end="")

    async def clear_input(self, t: Terminal) -> None:
        """Clear the input line (print a lot of whitespaces)."""
        text = ""
        await self.display_prompt(text, t)

    async def display_prompt(self, text: str, t: Terminal) -> None:
        """Display text in the input prompt."""
        prompt_location = self.prompt_location()
        x_pos = prompt_location[0]
        y_pos = prompt_location[1]

        with t.hidden_cursor(), t.location(x_pos, y_pos):
            out = self.truncate_input(text, t)
            out = t.ljust(out, self.real_width)
            print(out, end="")

    def prompt_location(self) -> Tuple[int, int]:
        """Return x and y coordinates of prompt."""
        x_pos = (
            Terminal().length(self.prompt) + self.x + int("l" in self.margins)
        )
        y_pos = self.y + self.prompt_position

        return x_pos, y_pos

    def truncate_input(self, text: str, t: Terminal) -> str:
        """Truncate text to fit into the input box."""
        out = text
        if t.length(text) > self.real_width:
            out = text[t.length(text) - (self.real_width) + 1:]  # fmt: skip
            out = t.on_red("<") + out
            # fmt:skip
        return out

    async def render(self, t: Terminal) -> None:
        """Render the Tile."""
        with t.location(self.x, self.y), t.hidden_cursor():
            print(self.prompt, end="")

        prompt_location = self.prompt_location()
        print(t.move_xy(prompt_location[0], prompt_location[1]), end="")

    def input_filter(self, keystroke: keyboard.Keystroke) -> bool:
        """
        For keystroke, return whether it should be allowed as string input.

        This somewhat requires that the interface use special application
        keys to perform functions, as alphanumeric input intended for
        persisting could otherwise be interpreted as a command sequence.
        """
        if keystroke.is_sequence:
            # Namely, deny multi-byte sequences (such as '\x1b[A'),
            return False
        if ord(keystroke) < ord(" "):
            # or control characters (such as ^L),
            return False
        return True


class ChatTile(Tile):
    """Chat tile."""

    def __init__(
        self,
        chat_with: UserModel,
        identity: UserModel,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Init chat Tile."""
        Tile.__init__(self, *args, **kwargs)
        self._buffer: List[MessageModel] = []
        self.new_messages: Queue = Queue()
        self.chat_with = chat_with
        self.myself = identity

    @property
    def buffer(self) -> List[MessageModel]:
        """Buffer for loaded messages."""
        return self._buffer

    @buffer.setter
    async def buffer(self, buffer: List[MessageModel]) -> None:
        """Buffer for loaded messages."""
        self._buffer = buffer
        await self.on_buffer_change()

    async def add_message_to_buffer(self, mess: MessageModel) -> None:
        """Add new message to buffer (newly received for example)."""
        self._buffer.insert(0, mess)
        await self.on_buffer_change()

    async def on_buffer_change(self) -> None:
        """Something happens on buffer change."""
        # pass
        t = Terminal()
        await self.render(t)

    async def consume_input(self, inp: str, t: Terminal) -> None:
        """
        Consume user input.

        right not just add message to a queue, UI manager should
        recover it, and then send, put into DB etc
        """
        # for debug add message to buffer
        await self.add_message_to_buffer(
            MessageModel(
                from_user=UserModel(username="Alice", id="", color=""),
                to_user=UserModel(username="Alice", id="", color=""),
                body=inp,
                date=datetime.now(),
            )
        )

    async def render(self, t: Terminal) -> None:
        """Render the Tile."""
        await Tile.render(self, t)

        # construct message buffer
        buffer = []
        for mes in self._buffer:

            message = t.gray(mes.date.strftime("[%H:%M]"))
            user_color = getattr(t, mes.from_user.color)
            message += (
                t.gray("[")
                + user_color(mes.from_user.username)
                + t.gray("]> ")
                + str(mes.body)
            )

            wrapped = (
                t.wrap(message, self.real_width) if self.real_width > 0 else []
            )
            # we need to reverse because were printing from the bottom up
            if len(wrapped) > 0:
                wrapped.reverse()
                buffer += wrapped
            if len(buffer) >= self.real_height:
                break

        if len(buffer) > 0:
            # print messages
            for y in range(0 + 1, (self.real_height + 1)):  # +1 for title
                with t.hidden_cursor(), t.location(
                    (self.x + int("l" in self.margins)),
                    (
                        self.y
                        + int("u" in self.margins)
                        + self.real_height
                        + 1
                        - y
                    ),
                ):
                    if len(buffer) > y - 1:
                        print(buffer[y - 1], end="")
