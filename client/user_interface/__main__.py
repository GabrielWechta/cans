"""For CLI usage and debugging."""
import asyncio
import signal
from random import choice
from types import FrameType
from typing import Any, Callable, Mapping, Union
import concurrent, threading
import time
import os
import hashlib
from datetime import datetime

from blessed import Terminal

from ..user_interface import UserInterface
from .tiles import Tile, InputTile, ChatTile, HeaderTile
from .tiling_managers import MonadTallLayout
from .view import View
from ..models import UserModel, MessageModel

print("hello")

ui = UserInterface()

term = Terminal()
loop = asyncio.get_event_loop()

view = View(ui.term)

header = HeaderTile(name = "Title bar", title = term.red_underline("cans") + " secure messenger", width = term.width, height = 2, x = 0, y = 0, margins = "d")
monad = MonadTallLayout(
    width=term.width, height=term.height - 2 - 1, x=0, y=header.height, use_margins=True
)
footer = InputTile(name = "Input", width = term.width, height = 1, x = 0, y = monad.screen_rect.height + monad.screen_rect.y, margins = "")

alice = UserModel(username="Alice", id="123", color="none")
bob = UserModel(username="Bob", id=hashlib.md5("aa".encode('utf-8')).hexdigest(), color="red")

chat = ChatTile(
    name="* chat",
    chat_with=bob,
    title=f"Chat with {term.red('Bob')}"
)

messages = [
    MessageModel(from_user=alice, body=f"don't know... let's try:", date=datetime(2022, 3 ,21, 11, 36 ,15)),
    MessageModel(from_user=bob, body=f"Okay that's { term.lightgreen_bold('cool') }, but do we have markdown support?", date=datetime(2022, 3 ,21, 11, 35 ,43)),
    MessageModel(from_user=alice, body=term.blue_underline("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), date=datetime(2022, 3 ,21, 11, 34 ,42)),
    MessageModel(from_user=alice, body="Observe", date=datetime(2022, 3 ,21, 11, 34 ,35)),
    MessageModel(from_user=bob, body="No way dude", date=datetime(2022, 3 ,21, 11, 34 ,1)),
    MessageModel(from_user=alice, body="You know we can post links here?", date=datetime(2022, 3 ,21, 11, 33 ,53)),
    MessageModel(from_user=bob, body="What do you want", date=datetime(2022, 3 ,21, 11, 32 ,29)),
    MessageModel(from_user=alice, body="Hi", date=datetime(2022, 3 ,21, 11, 31 ,59)), 
    MessageModel(from_user=bob, body="Hello", date=datetime(2022, 3 ,21, 11, 31 ,52)),
]

buffer =[]
for i in range(0, len(messages)):
    asyncio.run(chat.add_message_to_buffer(messages[len(messages)-1-i]))


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
loop.run_until_complete(monad.render_all())

loop.run_until_complete(header.render())
loop.run_until_complete(footer.render())

# signal handling, it kinda works
signal.signal(signal.SIGWINCH, lambda x,y: loop.create_task(on_resize()))

footer.mode = ""

async def run_in_thread(task: Callable, *args, **kwargs) -> None:
    # it kinda works I guess somehow, prolly not thread safe
    # Run in a custom thread pool:
    pool = concurrent.futures.ThreadPoolExecutor()
    result = loop.run_in_executor(
        pool, task, *args, **kwargs)
    result = await result

cursorLock = threading.Lock()

loop.create_task(run_in_thread(footer.input, term, cursorLock))

def test2() -> None:
    """Eh it does steal the cursor, need to implement some kind of locks when rendering"""
    while True:
        message = MessageModel(from_user=bob, body="test message", date = datetime.now())
        asyncio.run(render_threadsafe(chat.add_message_to_buffer, message))
        #sleep(0.005)

async def render_threadsafe(render_func: Callable, *args, **kwargs) -> None:
    """Will have to implement something like that in the 'real' function."""
    cursorLock.acquire()
    future = await render_func(*args, **kwargs)
    cursorLock.release()

loop.create_task(run_in_thread(test2))

async def test() -> None:
    while True:
        inp = (footer.input_queue.get())
        mode = inp[0]
        inp = inp[1]
        
        cmd = None
        if mode == "layout" and inp in cmds_layout:
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
                    cursorLock.acquire()
                    cmd(Tile(choice(signs) + " name"))
                    cursorLock.release()
                elif cmd == monad.remove:
                    target = monad.focused
                    cursorLock.acquire()
                    try:
                        cmd(monad.tiles[target])
                    except IndexError:
                        pass
                    cursorLock.release()
                else:
                    cursorLock.acquire()
                    cmd()
                    cursorLock.release()
                if cmd in focus_cmds:
                    await render_threadsafe(monad.render_focus)
                else:
                    await render_threadsafe(monad.render_all)
        elif mode == "":
            await render_threadsafe(monad.current_tile.consume_input, inp)

loop.run_until_complete(test())

# print(monad.screen_rect[1])
# monad.layout_all()
