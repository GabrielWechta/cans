"""For CLI usage and debugging."""
import asyncio

from blessed import Terminal

from ..user_interface import UserInterface
from .tile import Tile
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
monad.add(chat)
asyncio.run(monad.render())
term.inkey()

monad.add(contacts)
asyncio.run(monad.render())
term.inkey()

monad.add(Tile("a"))
asyncio.run(monad.render())
term.inkey()

monad.add(Tile("x"))
asyncio.run(monad.render())
term.inkey()

monad.remove(chat)
asyncio.run(monad.render())
term.inkey()

monad.cmd_set_ratio(0.5)
asyncio.run(monad.render())
term.inkey()

monad.cmd_reset()
asyncio.run(monad.render())
term.inkey()

monad.cmd_maximize()
asyncio.run(monad.render())
term.inkey()

monad.add(chat)
asyncio.run(monad.render())
term.inkey()

monad.cmd_maximize()
asyncio.run(monad.render())
term.inkey()

monad.cmd_swap_left()
asyncio.run(monad.render())
term.inkey()

monad.cmd_swap_right()
asyncio.run(monad.render())
term.inkey()

monad.cmd_left()
asyncio.run(monad.render())
term.inkey()

monad.cmd_right()
asyncio.run(monad.render())
term.inkey()

monad.cmd_right()
asyncio.run(monad.render())
term.inkey()
# monad.add(chat)


info = ""
for x in monad.tiles:
    # x.print()
    info += x.info()

print(info)
with (term.location(0, 0)):
    term.inkey()
# print(monad.screen_rect[1])
# monad.layout_all()
