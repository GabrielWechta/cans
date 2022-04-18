"""Tile classes for emulating independent I/O widgets of specified size."""

from blessed import Terminal
from ..models import MessageModel, UserModel
from datetime import datetime
from queue import Queue
from typing import List
import threading
import os
import math

class Tile:
    """Tile class for emulating an independent I/O widget of specified size."""

    margin = {
        "l": "|",
        "r": "|",
        "u": "-",
        "d": "-",
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
        return self._width

    @width.setter
    def width(self, width: int) -> None:
        self._width = width
        self.real_size()

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, height: int) -> None:
        self._height = height
        self.real_size()

    async def consume_input(self, inp: str) -> None:
        """Consume some input in some way."""
        self.body = inp
        await self.render()

    def real_size(self) -> None:
        """Calculate real size, excluding margins"""
        width = (
            self._width - int("l" in self.margins) - int("r" in self.margins)
        )
        height = (
            self._height - int("u" in self.margins) - int("d" in self.margins)
        ) - 1 #for titlebar

        self.real_width = width
        self.real_height = height

    def truncate(self, text: str, t: Terminal) -> str:
        """Truncate text to fit into the rendering box."""
        out = text
        if len(text) > self.real_width:
            out = t.truncate(text, self.real_width - 1)
            out += t.on_white('>')
        return out

    async def render(self) -> None:
        """Render the Tile."""
        
        sign = self.name[0]
        t = Terminal()

        # render title bar
        await self.render_titlebar(t)

        # for now just fill the Tile with some symbol
        for y in range(0 + 1, (self.real_height + 1)): # +1 for title
            with t.hidden_cursor(), t.location((self.x + int("l" in self.margins)), (self.y + int("u" in self.margins) + y)):
                out = (self.real_width) * " "
                if not self.focused:
                    print(out, end="")
                else:
                    print(out, end="")
                    # print(t.red(out), end="")
        with t.hidden_cursor(), t.location((self.x + int("l" in self.margins)), (self.y + int("u" in self.margins) + 1)):
            print(self.truncate(str(self.body), t))
        # print margins
        await self.render_margins(t)

    async def render_titlebar(self, t:Terminal) -> None:
        """Render title bar of a Tile"""
        with t.hidden_cursor(), t.location(self.x + int("l" in self.margins), self.y):
            if self.title != "":
                out = self.title + " " * (self._width - len(self.title) - 1)
                print(self.truncate(out, t), end="")
            else:
                out = self.name + " " * (self._width - len(self.name) - 1)
                print(self.truncate(out, t), end="")

    async def render_margins(self, t: Terminal) -> None:
        """Render margins of a tile."""
        attr = "red" if self.focused else "normal"

        color = getattr(t, attr)
        if "l" in self._margins:
            for y in range(0, (self._height)):
                with t.hidden_cursor(),t.location((self.x), (self.y + y)):
                    out = self.margin["l"]
                    print(color + out, end="")
        if "r" in self._margins:
            for y in range(0, (self._height)):
                with t.hidden_cursor(),t.location((self.x + self._width - 1), (self.y + y)):
                    out = self.margin["r"]
                    print(color + (out), end="")
        if "d" in self._margins:
            with t.hidden_cursor(),t.location((self.x), (self.y + self._height - 1)):
                out = (self._width) * self.margin["d"]
                print(color + (out), end="")
        if "u" in self._margins:
            with t.hidden_cursor(),t.location((self.x), (self.y)):
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
    """Header Tile"""

    async def render(self) -> None:
        """Render the Tile."""
        t = Terminal()
        await self.render_margins(t)
        await self.render_titlebar(t)
        

class InputTile(Tile):
    """Input Tile"""
    def __init__(self, prompt = "> ", *args, **kwargs) -> None:
        """Init input Tile"""
        self.prompt = prompt
        Tile.__init__(self, *args, **kwargs)
        self.input_queue = Queue()
        self.prompt_position = math.floor(self.real_height / 2)
        
        self.mode = ""

    def real_size(self) -> None:
        """Calculate real size, excluding margins"""
        width = (
            self._width - int("l" in self.margins) - int("r" in self.margins)
        ) - len(self.prompt) 
        height = (
            self._height - int("u" in self.margins) - int("d" in self.margins)
        ) - 1 #for titlebar
        
        self.real_width = width
        self.real_height = height
        

    def input(self, term: Terminal, lock: threading.Lock) -> None:
        """Input function, REALLY BAD TODO: think about better implementation."""
        inp = ""
        
        # basically run forever
        while True:
            #set cursor position
            with term.raw(), term.location(len(self.prompt) + self.x + int("l" in self.margins) + len(inp), self.y + self.prompt_position):
                # paste handling, use the first character to check
                # command type and add rest as additional input
                val = term.inkey()
                next = term.inkey(timeout=0.001)
                add_input = ""
                while next and self.input_filter(next):
                    add_input += next
                    next = term.inkey(timeout=0.001)
            
                # workaround to have a working ctrl+c in raw mode
                # and with threads
                if val == chr(3):
                    os._exit(1)
                # if normal mode
                if self.mode == "":
                    if val.code == term.KEY_ESCAPE:
                        self.mode = "layout"
                        lock.acquire()
                        self.clear_input(term)
                        lock.release()
                    else:
                        # if enter was pressed, return input
                        if val.code == term.KEY_ENTER:
                            self.input_queue.put((self.mode, inp))
                            lock.acquire()
                            self.clear_input(term)
                            lock.release()
                            inp = ""
                        elif val.code == term.KEY_BACKSPACE or val.code == term.KEY_DELETE:
                            lock.acquire()
                            self.clear_input(term)
                            lock.release()
                            inp = inp[:-1]
                        elif self.input_filter(val):
                            inp += val + add_input
                        lock.acquire()
                        self.display_prompt(inp, term)
                        lock.release()
                # if layout mode
                elif self.mode == "layout":
                    if val.code == term.KEY_ENTER:
                        self.mode = ""
                        lock.acquire()
                        self.clear_input(term)
                        lock.release()
                    else:
                        if self.input_filter(val) or not val.code:
                            self.input_queue.put((self.mode, val))
                            inp = ""
                        else:
                            self.input_queue.put((self.mode, val.code)) 
                            inp = ""

    def clear_input(self, t: Terminal) -> None:
        text = (self.real_width) * " "
        self.display_prompt(text, t)

    def display_prompt(self, text: str, t: Terminal) -> None:
        x_pos = len(self.prompt) + self.x + int("l" in self.margins)
        y_pos = self.y + self.prompt_position
        with t.location(x_pos, y_pos):
            print(self.truncate_input(text, t), end="")

    def truncate_input(self,text: str, t: Terminal) -> None:
        """Truncate text to fit into the input box."""
        out = text
        if len(text) > self.real_width:
            out = t.on_white('<') + ''
            out += text[len(text) - (self.real_width) + 1:]
        return out        

    async def render(self) -> None:
        """Render the Tile."""
        t = Terminal()
        with t.location(self.x, self.y), t.hidden_cursor():
            print(self.prompt, end="")
        print(t.move_xy(len(self.prompt) + self.x + int("l" in self.margins), self.y + self.prompt_position), end="")

    def input_filter(self, keystroke) -> str:
        """
        For given keystroke, return whether it should be allowed as string input.

        This somewhat requires that the interface use special application keys to perform functions, as
        alphanumeric input intended for persisting could otherwise be interpreted as a command sequence.
        """
        if keystroke.is_sequence:
            # Namely, deny multi-byte sequences (such as '\x1b[A'),
            return False
        if ord(keystroke) < ord(u' '):
            # or control characters (such as ^L),
            return False
        return True

class ChatTile(Tile):
    """Chat tile."""

    def __init__(self, chat_with: UserModel, *args, **kwargs) -> None:
        """Init chat Tile"""
        Tile.__init__(self, *args, **kwargs)
        self._buffer = []
        self.new_messages = Queue()
        self.chat_with = chat_with

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
        """Add new message to buffer (newly received for example)"""
        self._buffer.insert(0,mess)
        await self.on_buffer_change()

    async def on_buffer_change(self) -> None:
        """Something happens on buffer change."""
        #pass
        await self.render()

    async def consume_input(self, inp: str) -> None:
        """
        Consume user input.
        
        right not just add message to a queue, UI manager should 
        recover it, and then send, put into DB etc
        """
        # for debug add message to buffer 
        await self.add_message_to_buffer(MessageModel(from_user=UserModel("Alice","",""), body=inp,date=datetime.now()))

    async def render(self) -> None:
        """Render the Tile."""

        t = Terminal()

        await Tile.render(self)

        # hardcoded identity
        myself = UserModel(username="Alice", id="123", color="none")

        # construct message buffer
        buffer = []
        for mes in self._buffer:
 
            message = t.gray(mes.date.strftime("[%H:%M]"))
            if mes.from_user.username == myself.username:
                message += (t.gray("[")  + t.green(mes.from_user.username) + t.gray("]> ") + str(mes.body))
            else:
                message += (t.gray("[")  + t.red(mes.from_user.username) + t.gray("]> ") + str(mes.body))

            wrapped = t.wrap(message, self.real_width) if self.real_width > 0 else []
            # we need to reverse because were printing from the bottom up
            if len(wrapped) >0:
                wrapped.reverse()
                buffer += wrapped
            if len(buffer) >= self.real_height:
                break
        
        if len(buffer) > 0:
            # print messages
            for y in range(0 + 1, (self.real_height + 1)): # +1 for title
                with t.hidden_cursor(), t.location((self.x + int("l" in self.margins)), (self.y + int("u" in self.margins) + self.real_height + 1 - y)):
                    if len(buffer) > y-1:
                        print(buffer[y-1], end="")

