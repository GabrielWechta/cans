"""
View class for user interface.

Divides terminal into independent windows
"""

from blessed import Terminal

from .tiles import Tile


class View:
    """
    A class representing current View of the application.

    Contains a list of active Tiles and controls their layout
    """

    def __init__(self, term: Terminal) -> None:
        """Instantiate a view."""
        self.main_tile = []

        # create a chat box tile
        self.main_tile.append(
            Tile(
                "chat",
            )
        )
        # create a contacts tile
        self.main_tile.append(
            Tile(
                "contacts",
            )
        )

        # create a titlebar -- always in header
        self.header = Tile("titlebar")

        # create a input tile -- always in the footer
        self.footer = Tile("input")

        for tile in self.main_tile:
            print(tile.info())

        pass
