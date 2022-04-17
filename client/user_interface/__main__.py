"""For CLI usage and debugging."""
import asyncio
import signal
from random import choice
from types import FrameType
from typing import Any, Callable, Mapping, Union

from blessed import Terminal

from ..user_interface import UserInterface
from .tiles import Tile, InputTile, ChatTile, HeaderTile
from .tiling_managers import MonadTallLayout
from .view import View

print("hello")

ui = UserInterface()

term = Terminal()

view = View(ui.term)

header = HeaderTile(name = "Title bar", title = term.red_underline("cans") + " secure messenger", width = term.width, height = 2, x = 0, y = 0, margins = "d")
monad = MonadTallLayout(
    width=term.width, height=term.height - 2 - 1, x=0, y=header.height, use_margins=True
)
footer = InputTile(name = "Input", width = term.width, height = 1, x = 0, y = monad.screen_rect.height + monad.screen_rect.y, margins = "")

chat = Tile(
    "* chat",
)
contacts = Tile(
    "d contacts test test test",
)

# Test on resize signal


async def on_resize(
) -> None:
    """Test function for on_resize events."""
    monad.screen_rect_change(width=term.width, height=term.height - 2 - 1, x=0, y=header.height)
    header.width = term.width
    footer.y = monad.screen_rect.height + monad.screen_rect.y
    footer.width = term.width
    await (monad.render_all())
    await (footer.render())
    await (header.render())

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
    with term.location(0, term.height):
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
monad.add(Tile("a name"))
monad.add(Tile("x names"))
asyncio.run(monad.render_all())

asyncio.run(header.render())
asyncio.run(footer.render())

# signal handling it kinda works
signal.signal(signal.SIGWINCH, lambda x,y: asyncio.create_task(on_resize()))

footer.mode = ""
while True:
    asyncio.run(footer.input(term))

    inp = asyncio.run(footer.input_queue.get())[1]
    
    cmd = None
    if inp in cmds_layout:
        cmd = cmds_layout[inp]
    if cmd:
        focus_cmds = [
            monad.cmd_down,
            monad.cmd_up,
            monad.cmd_left,
            monad.cmd_right,
        ]
        if cmd == chr(3):
            break
                
        if cmd == monad.add:
            cmd(Tile(choice(signs) + " name"))
        elif cmd == monad.remove:
            target = monad.focused
            try:
                cmd(monad.tiles[target])
            except IndexError:
                pass
        else:
            cmd()
        if cmd in focus_cmds:
            asyncio.run(monad.render_focus())
        else:
            asyncio.run(monad.render_all())


# print(monad.screen_rect[1])
# monad.layout_all()
