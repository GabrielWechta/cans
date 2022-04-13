"""Tile class for emulating an independent I/O widget of specified size."""
from dataclasses import dataclass

from blessed import Terminal


@dataclass
class Tile:
    """Tile class for emulating an independent I/O widget of specified size."""

    def __init__(
        self,
        name: str,
        default_width: int = 0,
        default_height: int = 0,
        min_width: int = None,
        max_width: int = None,
        min_height: int = None,
        max_height: int = None,
        x: int = 0,
        y: int = 0,
    ) -> None:
        """Instantiate a screen."""
        self.name = name

        self.default_height = default_height
        self.default_width = default_width
        self.min_height = min_height
        self.max_height = max_height
        self.min_width = min_width
        self.max_width = max_width

        self.x = x
        self.y = y

        self.width = default_width
        self.height = default_height

    def print(self) -> None:
        """Print the Tile."""
        t = Terminal()
        sign = self.name[0]
        for y in range(0, (self.height)):
            with t.location((self.x), (self.y + y)):
                out = (self.width) * str(sign)
                print(out, end="")

    def info(self) -> str:
        """Return Tile info."""
        return f"""
Tile            {self.name}
x:              {self.x}
y:              {self.y}

width:          {self.width}
min_width:      {self.min_width}
max_width:      {self.max_height}
default_width:  {self.default_width}

height:         {self.height}
min_height:     {self.min_height}
max_height:     {self.max_height}
default_height: {self.default_height}
        """
