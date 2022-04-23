"""TileList class."""
from builtins import slice
from collections.abc import Iterator
from typing import List, Optional, Union, overload

from .tiles import Tile


class TileList:
    """
    A wrapper for a list of Tiles.

    Contains methods to control their behaviour,
    i.e. focusing, changing places etc.
    """

    def __init__(self) -> None:
        """Init the tileList."""
        self.current_id = 0
        self.tiles: List[Tile] = []

    @property
    def current_index(self) -> int:
        """Get current (focused tile) index."""
        return self.current_id

    @current_index.setter
    def current_index(self, x: int) -> int:
        if len(self):
            self.current_id = abs(x % len(self))
        else:
            self.current_id = 0
        return self.current_id

    @property
    def current_tile(self) -> Optional[Tile]:
        """Getter for current tile."""
        if not self.tiles:
            return None
        return self.tiles[self.current_id]

    @current_tile.setter
    def current_tile(self, tile: Tile) -> None:
        """Setter for current tile."""
        i = self.tiles.index(tile)
        self.current_id = i

    def focus(self, tile: Tile) -> None:
        """
        Mark the given tile as the current focused tile in collection.

        This is equivalent to setting current_tile.
        """
        self.current_tile = tile

    def focus_first(self) -> Tile:
        """Return the first tile in collection."""
        return self[0]

    def focus_next(self, tile: Tile) -> Optional[Tile]:
        """Return the tile next from tile in collection or None."""
        try:
            return self[self.index(tile) + 1]
        except IndexError:
            return None

    def focus_last(self) -> Tile:
        """Return the last tile in collection."""
        return self[-1]

    def focus_previous(self, tile: Tile) -> Optional[Tile]:
        """Return the tile previous to tile in collection or None."""
        i = self.index(tile)
        if i > 0:
            return self[i - 1]
        return None

    def add(
        self, tile: Tile, offset_to_current: int = 0, tile_position: str = ""
    ) -> None:
        """
        Insert the given tile into collection at position of the current.

        Use parameter 'offset_to_current' to specify where the tile shall be
        inserted. Defaults to zero, which means at position of current tile.
        Positive values are after the tile.
        Use parameter 'tile_position' to insert the given tile at 4 specific
        positions: top, bottom, after_current, before_current.
        """
        if tile_position != "":
            if tile_position == "after_current":
                return self.add(tile, offset_to_current=1)
            elif tile_position == "before_current":
                return self.add(tile, offset_to_current=0)
            elif tile_position == "top":
                self.append_head(tile)
            else:  # ie tile == "bottom"
                self.append(tile)
        else:
            pos = max(0, self.current_id + offset_to_current)
            if pos < len(self.tiles):
                self.tiles.insert(pos, tile)
            else:
                self.tiles.append(tile)
        self.current_tile = tile

    def append_head(self, tile: Tile) -> None:
        """Append the given tile in front of list."""
        self.tiles.insert(0, tile)

    def append(self, tile: Tile) -> None:
        """Append the given tile to the end of the collection."""
        self.tiles.append(tile)

    def remove(self, tile: Tile) -> None:
        """Remove the given tile from collection."""
        if tile not in self.tiles:
            return
        idx = self.tiles.index(tile)
        del self.tiles[idx]
        if len(self) == 0:
            self.current_id = 0
        elif idx <= self.current_id:
            self.current_id = max(0, self.current_id - 1)

    def rotate_up(self, maintain_index: bool = True) -> None:
        """
        Rotate the list up.

        The first tile is moved to last position.
        If maintain_index is True the current_index is adjusted,
        such that the same tile stays current and goes up in list.
        """
        if len(self.tiles) > 1:
            self.tiles.append(self.tiles.pop(0))
            if maintain_index:
                self.current_id -= 1

    def rotate_down(self, maintain_index: bool = True) -> None:
        """
        Rotate the list down.

        The last tile is moved to first position.
        If maintain_index is True the current_index is adjusted,
        such that the same tile stays current and goes down in list.
        """
        if len(self.tiles) > 1:
            self.tiles.insert(0, self.tiles.pop())
            if maintain_index:
                self.current_id += 1

    def swap(self, c1: Tile, c2: Tile, focus: int = 1) -> None:
        """
        Swap the two given tiles in list.

        The optional argument 'focus' can be 1, 2 or anything else.
        In case of 1, the first client c1 is focused, in case of 2 the c2 and
        the current_index is not changed otherwise.
        """
        i1 = self.tiles.index(c1)
        i2 = self.tiles.index(c2)
        self.tiles[i1], self.tiles[i2] = self.tiles[i2], self.tiles[i1]
        if focus == 1:
            self.current_id = i1
        elif focus == 2:
            self.current_id = i2

    def shuffle_up(self, maintain_index: bool = True) -> None:
        """
        Shuffle the list. The current tile swaps position with its predecessor.

        If maintain_index is True the current_index is adjusted,
        such that the same tile stays current and goes up in list.
        """
        idx = self.current_id
        if idx > 0:
            self.tiles[idx], self.tiles[idx - 1] = self[idx - 1], self[idx]
            if maintain_index:
                self.current_id -= 1

    def shuffle_down(self, maintain_index: bool = True) -> None:
        """
        Shuffle the list. The current tile swaps position with its successor.

        If maintain_index is True the current_index is adjusted,
        such that the same tile stays current and goes down in list.
        """
        idx = self.current_id
        if idx + 1 < len(self.tiles):
            self.tiles[idx], self.tiles[idx + 1] = self[idx + 1], self[idx]
            if maintain_index:
                self.current_id += 1

    def index(self, tile: Tile) -> int:
        """Return index of Tile."""
        return self.tiles.index(tile)

    def __len__(self) -> int:
        """Inner method."""
        return len(self.tiles)

    @overload
    def __getitem__(self, i: int) -> Tile:
        """Inner method."""
        ...

    @overload
    def __getitem__(self, i: slice) -> List[Tile]:
        """Inner method."""
        ...

    def __getitem__(self, i: Union[int, slice]) -> Union[Tile, List[Tile]]:
        """Inner method."""
        try:
            return self.tiles[i]
        except IndexError:
            raise IndexError("Index error for tile lists!")

    def __setitem__(self, i: int, value: Tile) -> None:
        """Inner method."""
        self.tiles[i] = value

    def __iter__(self) -> Iterator[Tile]:
        """Inner method."""
        return self.tiles.__iter__()

    def __contains__(self, tile: Tile) -> bool:
        """Inner method."""
        return tile in self.tiles

    def __str__(self) -> str:
        """Inner method."""
        curr = self.current_tile
        return "Tile collection: " + ", ".join(
            [("[%s]" if c == curr else "%s") % c.name for c in self.tiles]
        )
