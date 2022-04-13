"""For CLI usage and debugging."""
from blessed import Terminal

from ..user_interface import UserInterface
from .tile import Tile
from .view import MonadTallLayout, View

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
    name="d",
)
monad.add(chat)
term.inkey()
monad.add(contacts)
term.inkey()
monad.add(Tile("a"))
term.inkey()
monad.add(Tile("x"))
term.inkey()
monad.remove(chat)
term.inkey()
# monad.add(chat)

print(term.move_up(1))

info = ""
for x in monad.tiles:
    # x.print()
    info += x.info()

print(info)
with (term.location(0, 0)):
    term.inkey()
# print(monad.screen_rect[1])
# monad.layout_all()
