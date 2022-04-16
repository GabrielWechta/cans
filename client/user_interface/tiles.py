"""Tile class for emulating an independent I/O widget of specified size."""

from blessed import Terminal


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
    ) -> None:
        """Instantiate a screen."""
        self.name = name

        self.x = x
        self.y = y

        self.width = width
        self.height = height
        self.margins = ""

    async def render(self, focused: bool = False) -> None:
        """Render the Tile."""
        t = Terminal()
        sign = self.name[0]

        width = (
            self.width - int("l" in self.margins) - int("r" in self.margins)
        )
        height = (
            self.height - int("u" in self.margins) - int("d" in self.margins)
        )

        # for now just fill the Tile with some symbol
        for y in range(0, (height)):
            with t.location((self.x), (self.y + int("u" in self.margins) + y)):
                out = (width) * str(sign)
                if not focused:
                    print(out, end="")
                else:
                    print(t.red(out), end="")

        # print margins
        await self.render_margins(t)

    async def render_margins(self, t: Terminal) -> None:
        """Render margins of a tile."""
        if "l" in self.margins:
            for y in range(0, (self.height)):
                with t.location((self.x), (self.y + y)):
                    out = self.margin["l"]
                    print(out, end="")
        if "r" in self.margins:
            for y in range(0, (self.height)):
                with t.location((self.x + self.width - 1), (self.y + y)):
                    out = self.margin["r"]
                    print(out, end="")
        if "d" in self.margins:
            with t.location((self.x), (self.y + self.height - 1)):
                out = (self.width) * self.margin["d"]
                print(out, end="")
        if "u" in self.margins:
            with t.location((self.x), (self.y)):
                out = (self.width) * self.margin["u"]
                print(out, end="")

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
