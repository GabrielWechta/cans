"""For CLI usage and debugging."""
import asyncio
import signal

from blessed import Terminal
from random import choice

from ..user_interface import UserInterface
from .tiles import Tile
from .tiling_managers import MonadTallLayout
from .view import View

print("hello")

ui = UserInterface()

ui.say_hello()
print(ui.term)

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
def on_resize(*args) -> None:
    monad.screen_rect_change(width=term.width, height=term.height, x=0, y=0)
signal.signal(signal.SIGWINCH, on_resize)

signs= "qwertyuiopasdfghjklzxcvbnm1234567890!@#$%^&*()"

# Test mapping of keys to commands
cmds_layout = {
    term.KEY_LEFT:  monad.cmd_left,
    term.KEY_RIGHT: monad.cmd_right,
    term.KEY_DOWN:  monad.cmd_down,
    term.KEY_UP:    monad.cmd_up,

    term.KEY_SLEFT:  monad.cmd_swap_left,
    term.KEY_SRIGHT: monad.cmd_swap_right,
    term.KEY_SDOWN:  monad.cmd_shuffle_down,
    term.KEY_SUP:    monad.cmd_shuffle_up,

    ' ':            monad.cmd_flip,
    'q':            monad.cmd_grow,
    'w':            monad.cmd_shrink,
    'e':            monad.cmd_normalize,
    'r':            monad.cmd_maximize,


    # ctrl+a
    chr(1):         monad.add,
    # ctrl+d
    chr(4):         monad.remove,
}

# Prototype for input function
def input():
    with term.cbreak():
        val = ''
        val = term.inkey()
        #print(val.name)
        if val.is_sequence:
            out = (val.code)
        else:
            out = (val)
    return out

monad.add(chat)
monad.add(contacts)
monad.add(Tile("a"))
monad.add(Tile("x"))

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
            except:
                pass
        else:
            cmd()
    asyncio.run(monad.render())


info = ""
for x in monad.tiles:
    # x.print()
    info += x.info()

print(info)
with (term.location(0, 0)):
    term.inkey()
# print(monad.screen_rect[1])
# monad.layout_all()
