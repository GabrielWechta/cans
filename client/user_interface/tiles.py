"""Tile class for emulating an independent I/O widget of specified size."""

from blessed import Terminal
from ..models import MessageModel
from typing import List

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

        self._margins = ""
        self._height = 0
        self._width = 0
        self.width = width
        self.height = height
        self.focused = False
        self.title = title
        self.real_size()

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

    def truncate(self, text: str, color: str = "") -> str:
        out = text
        if len(text) > self.real_width:
            out = text[:self.real_width - 1]
            out += color +'>'
        return out

    async def render(self) -> None:
        """Render the Tile."""
        
        sign = self.name[0]
        t = Terminal()

        # render title bar
        await self.render_titlebar(t)

        # for now just fill the Tile with some symbol
        for y in range(0 + 1, (self.real_height + 1)): # +1 for title
            with t.location((self.x), (self.y + int("u" in self.margins) + y)):
                out = (self.real_width) * str(sign)
                if not self.focused:
                    print(out, end="")
                else:
                    print(out, end="")
                    # print(t.red(out), end="")

        # print margins
        await self.render_margins(t)

    async def render_titlebar(self, t:Terminal) -> None:
        """Render title bar of a Tile"""
        with t.location(self.x, self.y):
            if self.title != "":
                print(self.truncate(self.title, t.on_white), end="")
            else:
                print(self.truncate(self.name, t.on_white), end="")

    async def render_margins(self, t: Terminal) -> None:
        """Render margins of a tile."""
        attr = "red" if self.focused else "normal"

        color = getattr(t, attr)
        if "l" in self._margins:
            for y in range(0, (self._height)):
                with t.location((self.x), (self.y + y)):
                    out = self.margin["l"]
                    print(color + out, end="")
        if "r" in self._margins:
            for y in range(0, (self._height)):
                with t.location((self.x + self._width - 1), (self.y + y)):
                    out = self.margin["r"]
                    print(color + (out), end="")
        if "d" in self._margins:
            with t.location((self.x), (self.y + self._height - 1)):
                out = (self._width) * self.margin["d"]
                print(color + (out), end="")
        if "u" in self._margins:
            with t.location((self.x), (self.y)):
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

class ChatTile(Tile):
    """Chat tile."""

    def __init__(
        self,
        name: str,
        width: int = 0,
        height: int = 0,
        x: int = 0,
        y: int = 0,
        margins: str = "",
    ) -> None:
        """Insantiate a Chat Tile."""
        Tile.__init__(self, name=name, width=width, height=height, x=x, y=y, margins=margins)
        self._buffer: List[MessageModel] = []
        

    @property
    def buffer(self) -> List[MessageModel]:
        """Buffer for loaded messages."""
        return self._buffer

    @buffer.setter
    def buffer(self, buffer: List[MessageModel]) -> None:
        """Buffer for loaded messages."""
        self._buffer = buffer
        self.on_buffer_change()

    def on_buffer_change(self) -> None:
        """Something happens on buffer load."""
        pass
