"""
View class for user interface.

Divides terminal into independent windows
"""

from typing import List

from blessed import Terminal

from .tile import Tile
from .tile_list import TileList


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

    To restore all secondary client windows to their default size ratios
    use the ``cmd_normalize`` method.

    To reset all client windows to their default sizes, including the primary
    window, use the ``cmd_reset`` method.

    Maximizing:

    To toggle a client window between its minimum and maximum sizes
    simply use the ``cmd_maximize`` on a focused client.

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
    default_ratio = 0.75
    """The percent of the screen-space the master pane should occupy
    by default."""
    min_ratio = 0.25
    """The percent of the screen-space the master pane should occupy
    at minimum."""
    max_ratio = 0.75
    """The percent of the screen-space the master pane should occupy
    at maximum."""
    min_secondary_size = 10
    """minimum size in pixel for a secondary pane window """
    align = _right
    """Which side master plane will be placed
    "(one of `_left` or `_right`)"""
    change_ratio = 0.05
    """Resize ratio"""
    change_size = 1
    """Resize change in pixels"""
    new_tile_position = "after_current"
    """Place new windows : "
        after_current - after the active window.
        before_current - before the active window,
        top - at the top of the stack,
        bottom - at the bottom of the stack"""

    def __init__(self, width: int, height: int, x: int, y: int) -> None:
        """Init the view."""
        self.relative_sizes: List[float] = []
        self.screen_rect = (width, height, x, y)

        print(self.screen_rect)
        self.tiles = TileList()

    def _get_relative_size_from_absolute(self, absolute_size: int) -> float:
        return absolute_size / self.screen_rect[1]

    def _get_absolute_size_from_relative(self, relative_size: float) -> int:
        return int(relative_size * self.screen_rect[1])

    def screen_rect_change(
        self, width: int, height: int, x: int, y: int
    ) -> None:
        """Set the screen rect and redraw the screen."""
        self.screen_rect = (width, height, x, y)
        self.layout_all()

    @property
    def focused(self) -> int:
        """Return focused Tile."""
        return self.tiles.current_id

    def add(self, tile: Tile) -> None:
        """Add tile to layout."""
        self.tiles.add(tile, tile_position=MonadTallLayout.new_tile_position)
        self._on_ratio_change()
        self.cmd_normalize()

    def remove(self, tile: Tile) -> None:
        """Remove tile from layout."""
        self.tiles.remove(tile)
        self._on_ratio_change()
        self.cmd_normalize()

    def layout_all(self) -> None:
        """Draw the entire layout."""
        # print(t.clear)
        # print(t.move(0,0))

        for tile in self.tiles:
            tile.print()

    def cmd_set_ratio(self, ratio: float) -> None:
        """Directly set the main pane ratio."""
        ratio = min(self.max_ratio, ratio)
        self.ratio = max(self.min_ratio, ratio)

        self._on_ratio_change()

        self.layout_all()

    def cmd_normalize(self, redraw: bool = True) -> None:
        """Evenly distribute screen-space among secondary tiles."""
        n = len(self.tiles) - 1  # exclude main tile, 0
        self.tiles[0].height = self.screen_rect[1]

        # if secondary tiles exist
        if n > 0 and self.screen_rect is not None:
            self.relative_sizes = [(1.0 / n)] * n

        self._on_secondary_height_change()
        # reset main pane ratio
        if redraw:
            self.layout_all()

    def cmd_reset(self, ratio: float = None, redraw: bool = True) -> None:
        """Reset Layout."""
        self.ratio = ratio or MonadTallLayout.default_ratio
        if self.align == MonadTallLayout._left:
            self.align = MonadTallLayout._right

        self._on_ratio_change()

        self.cmd_normalize(redraw)

    def _on_ratio_change(self) -> None:
        """Change x and width of tiles."""
        ratio = self.ratio

        # set main pane width
        self.tiles[0].width = round(ratio * self.screen_rect[0])
        # set the main pane position
        self.tiles[0].x = 0

        # set secondary pane width
        if len(self.tiles) > 1:
            for i in range(1, len(self.tiles)):
                tile = self.tiles[i]
                tile.width = round((1 - ratio) * self.screen_rect[0]) - 1
                tile.x = round(ratio * self.screen_rect[0])

    def _on_secondary_height_change(self) -> None:
        """Change y and height of tiles."""
        if len(self.tiles) > 1:
            for i in range(1, len(self.tiles)):
                tile = self.tiles[i]
                tile.height = round(
                    self.relative_sizes[i - 1] * self.screen_rect[1]
                )
                tile.y = (i - 1) * tile.height

    def _maximize_main(self) -> None:
        """Toggle the main pane between min and max size."""
        if self.ratio <= 0.5 * (self.max_ratio + self.min_ratio):
            self.ratio = self.max_ratio
        else:
            self.ratio = self.min_ratio

        self._on_ratio_change()
        self.layout_all()

    def _maximize_secondary(self) -> None:
        """Toggle the focused secondary pane between min and max size."""
        # n = len(self.tiles) - 2  # total shrinking tiles
        # total size of collapsed secondaries
        # collapsed_size = self.min_secondary_size * n
        nidx = self.focused - 1  # focused size index
        # total height of maximized secondary
        # maxed_size = self.group.screen.dheight - collapsed_size
        # if maximized or nearly maximized
        if (
            abs(
                self._get_absolute_size_from_relative(
                    self.relative_sizes[nidx]
                )
                #    - maxed_size
            )
            < self.change_size
        ):
            pass
            # minimize
            # self._shrink_secondary(
            #    self._get_absolute_size_from_relative(
            #        self.relative_sizes[nidx]
            #    )
            #   - self.min_secondary_size
            # )
        # otherwise maximize
        else:
            pass
            # self._grow_secondary(maxed_size)

    def cmd_maximize(self) -> None:
        """Grow the currently focused tile to the max size."""
        # if we have 1 or 2 panes or main pane is focused
        if len(self.tiles) < 3 or self.focused == 0:
            self._maximize_main()
        # secondary is focused
        else:
            self._maximize_secondary()
        self.layout_all()
