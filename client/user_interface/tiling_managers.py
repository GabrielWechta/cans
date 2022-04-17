"""Contains tiling manager classes used by View."""
import math
import operator
from collections import namedtuple
from functools import reduce
from typing import List, Optional

from blessed import Terminal

from .tile_list import TileList
from .tiles import Tile


class MonadTallLayout:
    """
    Emulate the behavior of XMonad's default tiling scheme.

    via:
    https://docs.qtile.org/en/v0.18.0/_modules/libqtile/layout/xmonad.html

    Main-Pane:
    A main pane that contains a single window takes up a vertical portion of
    the screen_rect based on the ratio setting. This ratio can be adjusted with
    the ``cmd_grow_main`` and ``cmd_shrink_main`` or, while the main pane is in
    focus, ``cmd_grow`` and ``cmd_shrink``.

    ::

        ---------------------
        |            |      |
        |            |      |
        |            |      |
        |            |      |
        |            |      |
        |            |      |
        ---------------------

    Using the ``cmd_flip`` method will switch which horizontal side the main
    pane will occupy. The main pane is considered the "top" of the stack.

        ---------------------
        |      |            |
        |      |            |
        |      |            |
        |      |            |
        |      |            |
        |      |            |
        ---------------------

    Secondary-panes:

    Occupying the rest of the screen_rect are one or more secondary panes.  The
    secondary panes will share the vertical space of the screen_rect however
    they can be resized at will with the ``cmd_grow`` and ``cmd_shrink``
    methods.  The other secondary panes will adjust their sizes to smoothly
    fill all of the space.

    ::

        ---------------------          ---------------------
        |            |      |          |            |______|
        |            |______|          |            |      |
        |            |      |          |            |      |
        |            |______|          |            |      |
        |            |      |          |            |______|
        |            |      |          |            |      |
        ---------------------          ---------------------

    Panes can be moved with the ``cmd_shuffle_up`` and ``cmd_shuffle_down``
    methods. As mentioned the main pane is considered the top of the stack;
    moving up is counter-clockwise and moving down is clockwise.

    The opposite is true if the layout is "flipped".

    ::

        ---------------------          ---------------------
        |            |  2   |          |   2   |           |
        |            |______|          |_______|           |
        |            |  3   |          |   3   |           |
        |     1      |______|          |_______|     1     |
        |            |  4   |          |   4   |           |
        |            |      |          |       |           |
        ---------------------          ---------------------


    Normalizing/Resetting:

    To restore all secondary tile windows to their default size ratios
    use the ``cmd_normalize`` method.

    To reset all tile windows to their default sizes, including the primary
    window, use the ``cmd_reset`` method.

    Maximizing:

    To toggle a tile window between its minimum and maximum sizes
    simply use the ``cmd_maximize`` on a focused tile.

    Suggested Bindings::

        Key([modkey], "h", lazy.layout.left()),
        Key([modkey], "l", lazy.layout.right()),
        Key([modkey], "j", lazy.layout.down()),
        Key([modkey], "k", lazy.layout.up()),
        Key([modkey, "shift"], "h", lazy.layout.swap_left()),
        Key([modkey, "shift"], "l", lazy.layout.swap_right()),
        Key([modkey, "shift"], "j", lazy.layout.shuffle_down()),
        Key([modkey, "shift"], "k", lazy.layout.shuffle_up()),
        Key([modkey], "i", lazy.layout.grow()),
        Key([modkey], "m", lazy.layout.shrink()),
        Key([modkey], "n", lazy.layout.normalize()),
        Key([modkey], "o", lazy.layout.maximize()),
        Key([modkey, "shift"], "space", lazy.layout.flip()),
    """

    _left = 0
    _right = 1
    _med_ratio = 0.5

    # no one asked + L + touch grass + no maidens + ratio
    ratio = 0.75
    """
    The percent of the screen-space the master pane should occupy
    """
    default_ratio = 0.75
    """
    The percent of the screen-space the master pane should occupy
    by default.
    """
    min_ratio = 0.25
    """
    The percent of the screen-space the master pane should occupy
    at minimum.
    """
    max_ratio = 0.85
    """
    The percent of the screen-space the master pane should occupy
    at maximum.
    """
    min_secondary_size = 1
    """Minimum size in pixel for a secondary pane window """
    align = _right
    """Which side master plane will be placed
    "(one of `_left` or `_right`)"""
    change_ratio = 0.05
    """Resize ratio"""
    change_size = 2
    """Resize change in pixels"""
    new_tile_position = "after_current"
    """
    Place new windows :
        after_current - after the active window.
        before_current - before the active window,
        top - at the top of the stack,
        bottom - at the bottom of the stack
    """
    screen_rect_tuple = namedtuple("screen_rect_tuple", "width height x y")
    """Named tuple structure for screen rect"""

    def __init__(
        self,
        width: int,
        height: int,
        x: int,
        y: int,
        use_margins: bool = False,
    ) -> None:
        """Init the view."""
        self.absolute_sizes: List[int] = []
        self.screen_rect = MonadTallLayout.screen_rect_tuple(
            width=width, height=height, x=x, y=y
        )
        self.tiles = TileList()
        self.align = MonadTallLayout.align
        self.ratio = MonadTallLayout.ratio

        self.use_margins = use_margins
        self.min_secondary_size += int(use_margins)
        self.max_displayed_windows = math.floor(self.screen_rect.height / self.min_secondary_size)
        

    # 'Hack' for linter coz it has a problem :)
    def clone(self) -> "MonadTallLayout":
        """Clone layout for other Views."""
        c = MonadTallLayout(
            width=self.screen_rect.width,
            height=self.screen_rect.height,
            x=self.screen_rect.x,
            y=self.screen_rect.y,
        )
        c.absolute_sizes = []
        c.screen_rect = self.screen_rect
        c.ratio = self.ratio
        c.align = self.align
        c.use_margins = self.use_margins
        return c

    def _get_relative_size_from_absolute(self, absolute_size: int) -> float:
        return absolute_size / self.screen_rect.height

    def _get_absolute_size_from_relative(self, relative_size: float) -> int:
        return math.floor(relative_size * self.screen_rect.height)

    def screen_rect_change(
        self, width: int, height: int, x: int, y: int
    ) -> None:
        """Set the screen rect and redraw the screen."""
        # Save relative sizes to preserve them
        relative_sizes = [
            self._get_relative_size_from_absolute(val)
            for val in self.absolute_sizes
        ]

        self.screen_rect = MonadTallLayout.screen_rect_tuple(
            width=width, height=height, x=x, y=y
        )
        self._relative_sizes_to_absolute(relative_sizes)

        self.max_displayed_windows = math.floor(self.screen_rect.height / self.min_secondary_size)
        
        self.layout_all()

    @property
    def focused(self) -> int:
        """Return focused Tile."""
        return self.tiles.current_id

    def add(self, tile: Tile) -> Optional[str]:
        """Add tile to layout."""
        if (len(self.tiles) > self.max_displayed_windows):
            return "Max amount of tiles reached"
        self.tiles.add(tile, tile_position=MonadTallLayout.new_tile_position)
        self.cmd_normalize()
        

    def remove(self, tile: Tile) -> None:
        """Remove tile from layout."""
        self.tiles.remove(tile)
        self.cmd_normalize()

    def layout_all(self) -> None:
        """Calculate the entire layout."""
        # Set main pane height
        try:
            self.tiles[0].height = self.screen_rect.height
            self.tiles[0].y = self.screen_rect.y
        except IndexError:
            return

        # Edge case, normalize if there are no absolute heights for sec. panes
        if not self.absolute_sizes:
            self.cmd_normalize(recalc=False)

        # Set secondary panes heights
        self._set_secondary_heights()

        # Set widths
        self._set_widths()

        # for tile in self.tiles:
        #    tile.render()

    def cmd_set_ratio(self, ratio: float) -> None:
        """Directly set the main pane ratio."""
        ratio = min(self.max_ratio, ratio)
        self.ratio = max(self.min_ratio, ratio)

        self.layout_all()

    def cmd_normalize(self, recalc: bool = True) -> None:
        """Evenly distribute screen-space among secondary tiles."""
        n = len(self.tiles) - 1  # exclude main tile, 0

        # if secondary tiles exist
        if n > 0 and self.screen_rect is not None:
            relative_sizes = [(1.0 / n)] * n
            self._relative_sizes_to_absolute(relative_sizes)

        # reset main pane ratio
        if recalc:
            self.layout_all()

    def _relative_sizes_to_absolute(self, relative_sizes: List[float]) -> None:
        """Calculate absolute sizes from a list of relative sizes (sum 1)."""
        n = len(relative_sizes)
        # check if screen can be distributed in its entirety
        calc_height = reduce(
            operator.add,
            [self._get_absolute_size_from_relative(a) for a in relative_sizes],
        )
        pads = [0] * n
        i = 0

        # if not then check if any of secondary panes is focused:
        if abs(calc_height - self.screen_rect.height) > 0:
            # if not then add/subtract 1 pixel to/from every
            # secondary pane until its ok
            while calc_height < self.screen_rect.height:
                amt = int(
                    math.copysign(1, self.screen_rect.height - calc_height)
                )
                pads[i] += amt
                i = (i + 1) % (n)
                calc_height += amt

        # calculate absolute sizes
        self.absolute_sizes = []
        for rel_val, pad in zip(relative_sizes, pads):
            self.absolute_sizes.append(
                self._get_absolute_size_from_relative(rel_val) + pad
            )
        # if any height is lesser than minimum, normalize heights
        #for val in self.absolute_sizes:
        #    if val < self.min_secondary_size:
        #        self.cmd_normalize()
        #        break
        

    def cmd_reset(self, ratio: float = None, redraw: bool = True) -> None:
        """Reset Layout."""
        self.ratio = ratio or MonadTallLayout.default_ratio
        if self.align == MonadTallLayout._left:
            self.align = MonadTallLayout._right

        self.cmd_normalize(redraw)

    def _set_widths(self) -> None:
        """Calculate x and width of all tiles."""
        ratio = self.ratio

        if len(self.tiles) > 1:
            # right alignment
            if self.align == MonadTallLayout._right:
                self.tiles[0].x = self.screen_rect.x
                # set main pane width
                self.tiles[0].width = math.ceil(ratio * self.screen_rect.width)
                # set secondary pane width and position
                for i in range(1, len(self.tiles)):
                    tile = self.tiles[i]
                    tile.width = math.floor(
                        (1.0 - ratio) * self.screen_rect.width
                    )
                    tile.x = self.tiles[0].width + self.screen_rect.x
            # left alignment
            else:
                sec_width = math.floor((1.0 - ratio) * self.screen_rect.width)
                self.tiles[0].x = sec_width + self.screen_rect.x
                # set main pane width
                self.tiles[0].width = math.ceil(ratio * self.screen_rect.width)
                # set secondary pane width and position
                for i in range(1, len(self.tiles)):
                    tile = self.tiles[i]
                    tile.width = sec_width
                    tile.x = self.screen_rect.x
        else:
            # set main pane width - fullscreen
            self.tiles[0].x = self.screen_rect.x
            self.tiles[0].width = self.screen_rect.width

    def _set_secondary_heights(self) -> None:
        """Calculate y and height of tiles."""
        if len(self.tiles) > 1:
            n = len(self.absolute_sizes) 
            # calculate absolute pixel height values and positions
            height = 0
            for i in range(0, n):
                tile = self.tiles[i + 1]
                tile.height = self.absolute_sizes[i]
                tile.y = height + self.screen_rect.y
                height += tile.height

    def _maximize_main(self) -> None:
        """Toggle the main pane between min and max size."""
        if self.ratio <= 0.5 * (self.max_ratio + self.min_ratio):
            self.ratio = self.max_ratio
        else:
            self.ratio = self.min_ratio

        self.layout_all()

    def _maximize_secondary(self) -> None:
        """Toggle the focused secondary pane between min and max size."""
        n = len(self.tiles) - 2  # total shrinking tiles
        # total size of collapsed secondaries
        collapsed_size = self.min_secondary_size * n
        nidx = self.focused - 1  # focused size index
        # total height of maximized secondary
        maxed_size = self.screen_rect.height - collapsed_size
        # if maximized or nearly maximized
        if abs(self.absolute_sizes[nidx] - maxed_size) < 1:
            # minimize
            self._shrink_secondary(
                self.absolute_sizes[nidx] - self.min_secondary_size
            )
        # otherwise maximize
        else:
            self._grow_secondary(maxed_size)

    def get_shrink_margin(self, i: int) -> int:
        """Return how many remaining pixels a tile can shrink."""
        return max(
            0,
            self.absolute_sizes[i] - self.min_secondary_size,
        )

    def shrink(self, i: int, amt: int) -> int:
        """
        Reduce the size of a tile.

        Will only shrink the tile until it reaches the configured minimum
        size. Any amount that was prevented in the resize is returned.
        """
        # get max resizable amount
        margin = self.get_shrink_margin(i)
        if amt > margin:  # too much
            self.absolute_sizes[i] -= margin
            return amt - margin
        else:
            self.absolute_sizes[i] -= amt
            return 0

    def shrink_up(self, idx: int, amt: int) -> int:
        """
        Shrink the tile up.

        Will shrink all secondary tile above the specified index in order.
        Each tile will attempt to shrink as much as it is able before the
        next tile is resized.

        Any amount that was unable to be applied to the tile is returned.
        """
        left = amt  # track unused shrink amount
        # for each tile before specified index
        for i in range(0, idx):
            # shrink by whatever is left-over of original amount
            left -= left - self.shrink(i, left)
        # return unused shrink amount
        return left

    def shrink_up_shared(self, idx: int, amt: int) -> int:
        """
        Shrink the shared space.

        Will shrink all secondary tiles above the specified index by an equal
        share of the provided amount. After applying the shared amount to all
        affected tiles, any amount left over will be applied in a non-equal
        manner with ``shrink_up``.

        Any amount that was unable to be applied to the tiles is returned.
        """
        # split shrink amount among number of tiles
        per_amt = math.ceil(amt / idx)
        left = amt  # track unused shrink amount
        # for each tile before specified index
        for i in range(0, idx):
            # shrink by equal amount and track left-over
            left -= per_amt - (self.shrink(i, per_amt))
        # apply non-equal shrinkage secondary pass
        # in order to use up any left over shrink amounts
        left = self.shrink_up(idx, (left))
        # return whatever could not be applied
        return left

    def shrink_down(self, idx: int, amt: int) -> int:
        """
        Shrink current tile down.

        Will shrink all secondary tiles below the specified index in order.
        Each tile will attempt to shrink as much as it is able before the
        next tile is resized.

        Any amount that was unable to be applied to the tiles is returned.
        """
        left = amt  # track unused shrink amount
        # for each tile after specified index
        for i in range(idx + 1, len(self.absolute_sizes)):
            # shrink by current total left-over amount
            left -= left - self.shrink(i, left)
        # return unused shrink amount
        return left

    def shrink_down_shared(self, idx: int, amt: int) -> int:
        """
        Shrink secondary tiles.

        Will shrink all secondary tiles below the specified index by an equal
        share of the provided amount. After applying the shared amount to all
        affected tiles, any amount left over will be applied in a non-equal
        manner with ``shrink_down``.

        Any amount that was unable to be applied to the tiles is returned.
        """
        # split shrink amount among number of tiles
        per_amt = math.ceil(amt / (len(self.absolute_sizes) - 1 - idx))
        left = amt  # track unused shrink amount
        # for each tile after specified index
        for i in range(idx + 1, len(self.absolute_sizes)):
            # shrink by equal amount and track left-over
            left -= per_amt - self.shrink(i, per_amt)
        # apply non-equal shrinkage secondary pass
        # in order to use up any left over shrink amounts
        left = self.shrink_down(idx, left)
        # return whatever could not be applied
        return left

    def _grow_main(self, amt: float) -> None:
        """Will grow the tile that is currently in the main pane."""
        self.ratio += amt
        self.ratio = min(self.max_ratio, self.ratio)

    def _grow_solo_secondary(self, amt: float) -> None:
        """Will grow the solitary tile in the secondary pane."""
        self.ratio -= amt
        self.ratio = max(self.min_ratio, self.ratio)

    def _grow_secondary(self, amt: int) -> None:
        """Will grow the focused tile in the secondary pane."""
        half_change_size = math.ceil(amt / 2)
        # track unshrinkable amounts
        left = amt
        # first secondary (top)
        if self.focused == 1:
            # only shrink downwards
            left -= amt - self.shrink_down_shared(0, amt)
        # last secondary (bottom)
        elif self.focused == len(self.tiles) - 1:
            # only shrink upwards
            left -= amt - self.shrink_up(len(self.absolute_sizes) - 1, amt)
        # middle secondary
        else:
            # get size index
            i = self.focused - 1
            # shrink up and down
            left -= half_change_size - self.shrink_up_shared(
                i, half_change_size
            )
            if left > 0:
                left -= half_change_size - self.shrink_down_shared(
                    i, half_change_size
                )
            if left > 0:
                left -= half_change_size - self.shrink_up_shared(
                    i, half_change_size
                )
            if left > 0:
                left -= half_change_size - self.shrink_down_shared(
                    i, half_change_size
                )
        # calculate how much shrinkage took place
        diff = amt - left
        # grow tile by diff amount
        self.absolute_sizes[self.focused - 1] += diff

    def cmd_maximize(self) -> None:
        """Grow the currently focused tile to the max size."""
        # if we have 1 or 2 panes or main pane is focused
        if len(self.tiles) < 3 or self.focused == 0:
            self._maximize_main()
        # secondary is focused
        else:
            self._maximize_secondary()
        self.layout_all()

    def cmd_grow(self) -> None:
        """
        Grow current tile.

        Will grow the currently focused tile reducing the size of those
        around it. Growing will stop when no other secondary tiles can reduce
        their size any further.
        """
        if self.focused == 0:
            self._grow_main(self.change_ratio)
        elif len(self.tiles) == 2:
            self._grow_solo_secondary(self.change_ratio)
        else:
            self._grow_secondary(self.change_size)
        self.layout_all()

    def cmd_grow_main(self) -> None:
        """
        Grow main pane.

        Will grow the main pane, reducing the size of tiles in the secondary
        pane.
        """
        self._grow_main(self.change_ratio)
        self.layout_all()

    def cmd_shrink_main(self) -> None:
        """
        Shrink main pane.

        Will shrink the main pane, increasing the size of tiles in the
        secondary pane.
        """
        self._shrink_main(self.change_ratio)
        self.layout_all()

    def grow(self, idx: int, amt: int) -> None:
        """Grow secondary tile by specified amount."""
        self.absolute_sizes[idx] += amt

    def grow_up_shared(self, idx: int, amt: int) -> None:
        """
        Grow higher secondary tiles.

        Will grow all secondary tiles above the specified index by an equal
        share of the provided amount.
        """
        # split grow amount among number of tiles
        per_amt = math.ceil(amt / idx)
        left = amt  # track unused grow amount

        # for each tile after specified index
        for i in range(0, idx):
            # shrink by equal amount and track left-over
            left -= per_amt
            if left > 0:
                self.grow(i, per_amt)
            # if this change would've grown too much
            else:
                self.grow(i, left + per_amt)
                break

    def grow_down_shared(self, idx: int, amt: int) -> None:
        """
        Grow lower secondary tiles.

        Will grow all secondary tiles below the specified index by an equal
        share of the provided amount.
        """
        # split grow amount among number of tiles
        per_amt = math.ceil(amt / (len(self.absolute_sizes) - 1 - idx))
        left = amt  # track unused grow amount

        # for each tile after specified index
        for i in range(idx + 1, len(self.absolute_sizes)):
            # shrink by equal amount and track left-over
            left -= per_amt
            if left > 0:
                self.grow(i, per_amt)
            # if this change would've grown too much
            else:
                self.grow(i, left + per_amt)
                break

    def _shrink_main(self, amt: float) -> None:
        """Will shrink the tile that currently in the main pane."""
        self.ratio -= amt
        self.ratio = max(self.min_ratio, self.ratio)

    def _shrink_solo_secondary(self, amt: float) -> None:
        """Will shrink the solitary tile in the secondary pane."""
        self.ratio += amt
        self.ratio = min(self.max_ratio, self.ratio)

    def _shrink_secondary(self, amt: int) -> None:
        """Will shrink the focused tile in the secondary pane."""
        # get focused tile
        tile = self.tiles[self.focused]

        # get default change size
        change = amt

        # get left-over height after change
        left = tile.height - amt
        # if change would violate min_secondary_size
        if left < self.min_secondary_size:
            # just reduce to min_secondary_size
            change = tile.height - self.min_secondary_size

        # calculate half of that change
        half_change_1 = math.floor(change / 2)
        half_change_2 = math.ceil(change / 2)

        # first secondary (top)
        if self.focused == 1:
            # only grow downwards
            self.grow_down_shared(0, change)
        # last secondary (bottom)
        elif self.focused == len(self.tiles) - 1:
            # only grow upwards
            self.grow_up_shared(len(self.absolute_sizes) - 1, change)
        # middle secondary
        else:
            i = self.focused - 1
            # grow up and down
            self.grow_up_shared(i, half_change_1)
            self.grow_down_shared(i, half_change_2)
        # shrink tiles by total change
        self.absolute_sizes[self.focused - 1] -= change

    def cmd_shrink(self) -> None:
        """
        Shrink current tile.

        Will shrink the currently focused tile reducing the size of those
        around it. Shrinking will stop when the tile has reached the minimum
        size.
        """
        if self.focused == 0:
            self._shrink_main(self.change_ratio)
        elif len(self.tiles) == 2:
            self._shrink_solo_secondary(self.change_ratio)
        else:
            self._shrink_secondary(self.change_size)
        self.layout_all()

    def cmd_shuffle_up(self) -> None:
        """Shuffle the tile up the stack."""
        self.tiles.shuffle_up()
        self.layout_all()
        target = self.tiles.current_tile
        if target:
            self.focus(target)

    def cmd_shuffle_down(self) -> None:
        """Shuffle the tile down the stack."""
        self.tiles.shuffle_down()
        self.layout_all()
        target = self.tiles.current_tile
        if target:
            self.focus(self.tiles[self.focused])

    def cmd_flip(self) -> None:
        """Flip the layout horizontally."""
        self.align = self._left if self.align == self._right else self._right
        self.layout_all()

    def _get_closest(
        self, x: int, y: int, tiles: List[Tile]
    ) -> Optional[Tile]:
        """Get closest tile to a point x,y."""
        target = min(
            tiles,
            key=lambda c: math.hypot(c.x - x, c.y - y),
            default=self.tiles.current_tile,
        )
        return target

    def cmd_swap(self, tile1: Tile, tile2: Tile) -> None:
        """Swap two tiles."""
        self.tiles.swap(c1=tile1, c2=tile2, focus=1)
        self.layout_all()
        self.focus(tile1)

    def cmd_swap_left(self) -> None:
        """Swap current tile with closest tile to the left."""
        tile = self.tiles.current_tile
        if tile:
            x, y = tile.x, tile.y
            candidates = [c for c in self.tiles if (c.x < x)]
            target = self._get_closest(x=x, y=y, tiles=candidates)
            if target:
                self.cmd_swap(tile, target)

    def cmd_swap_right(self) -> None:
        """Swap current tile with closest tile to the right."""
        tile = self.tiles.current_tile
        if tile:
            x, y = tile.x, tile.y
            candidates = [c for c in self.tiles if (c.x > x)]
            target = self._get_closest(x=x, y=y, tiles=candidates)
            if target:
                self.cmd_swap(tile, target)

    def cmd_swap_main(self) -> None:
        """Swap current tile to main pane."""
        if self.align == self._left:
            self.cmd_swap_left()
        elif self.align == self._right:
            self.cmd_swap_right()

    def cmd_left(self) -> None:
        """Focus on the closest tile to the left of the current tile."""
        tile = self.tiles.current_tile
        if tile:
            x, y = tile.x, tile.y
            candidates = [c for c in self.tiles if (c.x < x)]
            target = self._get_closest(x=x, y=y, tiles=candidates)
            if target:
                self.focus(target)

    def cmd_right(self) -> None:
        """Focus on the closest tile to the right of the current tile."""
        tile = self.tiles.current_tile
        if tile:
            x, y = tile.x, tile.y
            candidates = [c for c in self.tiles if (c.x > x)]
            target = self._get_closest(x=x, y=y, tiles=candidates)
            if target:
                self.focus(target)

    def focus(self, tile: Tile) -> None:
        """Focus selected tile."""
        self.tiles.current_tile = tile
        self.layout_all()

    def focus_first(self) -> Tile:
        """
        Return the first tile in Layout.

        It DOES NOT focus the tile itself, this is done by caller.
        """
        return self.tiles.focus_first()

    def focus_last(self) -> Tile:
        """
        Return the last tile in Layout.

        It DOES NOT focus the tile itself, this is done by caller.
        """
        return self.tiles.focus_last()

    def focus_next(self, tile: Tile) -> Optional[Tile]:
        """
        Return Tile after the supplied tile in Layout.

        It DOES NOT focus the tile itself, this is done by caller.
        """
        return self.tiles.focus_next(tile)

    def focus_previous(self, tile: Tile) -> Optional[Tile]:
        """
        Return Tile after the supplied tile in Layout.

        It DOES NOT focus the tile itself, this is done by caller.
        """
        return self.tiles.focus_previous(tile)

    def cmd_up(self) -> None:
        """Focus (select) the tile before the focused one."""
        if self.tiles.current_tile is None:
            return
        tile = (
            self.focus_previous(self.tiles.current_tile) or self.focus_last()
        )
        self.focus(tile)

    def cmd_down(self) -> None:
        """Focus (select) the tile after the focused one."""
        if self.tiles.current_tile is None:
            return
        tile = self.focus_next(self.tiles.current_tile) or self.focus_first()
        self.focus(tile)

    async def render_all(self) -> None:
        """Render all tiles on screen."""
        term = Terminal()
        if len(self.tiles) == 0:
            screen = self.screen_rect
            for y in range(0, (screen.height)):
                with term.location((screen.x), (screen.y + y)):
                    out = (screen.width) * " "
                    print(out, end="")
            return
        await self.render_main()
        await self.render_secondary()

    async def render_secondary(self) -> None:
        """Render secondary tiles on screen."""
        for tile in self.tiles[1:]:
            i1 = self.tiles.index(tile)
            i2 = self.tiles.current_index
            tile.focused = i1 == i2
            # Set margins if using them
            if self.use_margins:
                self.set_margins(tile)
            else:
                tile.margins = ""

            await tile.render()

    async def render_main(self) -> None:
        """Render main tile on screen."""
        tile = self.tiles[0]
        tile.focused = self.tiles.current_index == 0

        if self.use_margins:
            self.set_margins(tile)
        else:
            tile.margins = ""

        await tile.render()

    async def render_focus(self) -> None:
        """Render only the focus indicator on screen."""
        term = Terminal()
        for tile in self.tiles:
            i1 = self.tiles.index(tile)
            i2 = self.tiles.current_index
            tile.focused = i1 == i2
            await tile.render_focus(term)

    def set_margins(self, tile: Tile) -> None:
        """Set margins of a tile."""
        i = self.tiles.index(tile)
        if i == 0:
            margins = "rd" if self.align == MonadTallLayout._right else "ld"
        else:
            margins = "ld" if self.align == MonadTallLayout._right else "rd"

        tile.margins = margins
