"""For CLI usage and debugging."""
import asyncio
import signal
from random import choice
from types import FrameType
from typing import Any, Callable, Mapping, Union

from blessed import Terminal

from ..user_interface import UserInterface
from .tiles import Tile
from .tiling_managers import MonadTallLayout
from .view import View

print("hello")

ui = UserInterface()

term = Terminal()

view = View(ui.term)
monad = MonadTallLayout(width=term.width, height=term.height, x=0, y=0)
chat = Tile(
    "*",
)
contacts = Tile(
    "d",
)

# Test on resize signal
def on_resize(
    a1: Union[signal.Signals, FrameType],
    a2: Any,
) -> None:
    """Test function for on_resize events."""
    monad.screen_rect_change(width=term.width, height=term.height, x=0, y=0)
    asyncio.run(monad.render())

signal.signal(signal.SIGWINCH, on_resize)

signs = "qwertyuiopasdfghjklzxcvbnm1234567890!@#$%^&*()"
cmds_layout: Mapping[Any, Callable[..., None]] = {
    # arrow keys
    term.KEY_LEFT:  monad.cmd_left,
    term.KEY_RIGHT: monad.cmd_right,
    term.KEY_DOWN:  monad.cmd_down,
    term.KEY_UP:    monad.cmd_up,

    # arrow keys with shift
    term.KEY_SLEFT:     monad.cmd_swap_left,
    term.KEY_SRIGHT:    monad.cmd_swap_right,
    term.KEY_SDOWN:     monad.cmd_shuffle_down,
    term.KEY_SUP:       monad.cmd_shuffle_up,

    # normal letters
    ' ': monad.cmd_flip,
    'q': monad.cmd_grow,
    'w': monad.cmd_shrink,
    'e': monad.cmd_normalize,
    'r': monad.cmd_maximize,

    # ctrl+a
    chr(1):     monad.add,
    # ctrl+d
    chr(4):     monad.remove,
    # ctrl+r
    chr(17):    monad.cmd_reset,
}  # fmt: skip


def input() -> str:
    """Prototype for input function."""
    with term.location():
        with term.cbreak():
            val = term.inkey()
            # print(val.name)
            if val.is_sequence:
                out = val.code
            else:
                out = val
    return out


monad.add(chat)
monad.add(contacts)
monad.add(Tile("a"))
monad.add(Tile("x"))
asyncio.run(monad.render())

while True:
    inp = input()
    cmd = None
    if inp in cmds_layout:
        cmd = cmds_layout[inp]
    if cmd:
        if cmd == monad.add:
            cmd(Tile(choice(signs)))
        elif cmd == monad.remove:
            target = monad.focused
            try:
                cmd(monad.tiles[target])
            except IndexError:
                pass
        else:
            cmd()
    asyncio.run(monad.render())


# print(monad.screen_rect[1])
# monad.layout_all()
