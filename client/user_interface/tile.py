"""Tile class for emulating an independent I/O widget of specified size."""
from dataclasses import dataclass

from blessed import Terminal


@dataclass
class Tile:
    """Tile class for emulating an independent I/O widget of specified size."""

    def __init__(
        self,
        name: str,
        width: int = 0,
        height: int = 0,
        x: int = 0,
        y: int = 0,
        focused: bool = False,
    ) -> None:
        """Instantiate a screen."""
        self.name = name

        self.x = x
        self.y = y

        self.width = width
        self.height = height

        self.focused = focused

    async def render(self, focused: bool = False) -> None:
        """Render the Tile."""
        t = Terminal()
        sign = self.name[0]
        for y in range(0, (self.height)):
            with t.location((self.x), (self.y + y)):
                out = (self.width) * str(sign)
                if not focused:
                    print(out, end="")
                else:
                    print(t.red(out), end="")

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
