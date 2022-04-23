"""For CLI usage and debugging."""
import asyncio
import hashlib

from blessed import Terminal

from ..models import UserModel
from ..user_interface import UserInterface

# from .view import View


term = Terminal()
loop = asyncio.get_event_loop()

ui = UserInterface(loop)

eve = UserModel(
    username="Eve",
    id=hashlib.md5("ee".encode("utf-8")).hexdigest(),
    color="blue",
)

bob = UserModel(
    username="Bob",
    id=hashlib.md5("aa".encode("utf-8")).hexdigest(),
    color="red",
)

ui.view.add_chat(bob)
ui.view.add_chat(eve)
ui.view.add_chat(bob)


async def send_test_messages_from_bob() -> None:
    """Send some stuff from bob."""
    while True:
        await ui.on_new_message_received_str("test message", bob)
        await asyncio.sleep(2)


loop.create_task(send_test_messages_from_bob())

loop.run_forever()
# header = HeaderTile(
#     name="Title bar",
#     title=term.red_underline("cans") + " secure messenger",
#     width=term.width,
#     height=2,
#     x=0,
#     y=0,
#     margins="d",
# )
# monad = MonadTallLayout(
#     width=term.width,
#     height=term.height - 2 - 1,
#     x=0,
#     y=header.height,
#     term=term,
#     use_margins=True,
# )
# footer = InputTile(
#     name="Input",
#     width=term.width,
#     height=1,
#     x=0,
#     y=monad.screen_rect.height + monad.screen_rect.y,
#     margins="",
# )

# alice = UserModel(username="Alice", id="123", color="none")
# bob = UserModel(
#     username="Bob",
#     id=hashlib.md5("aa".encode("utf-8")).hexdigest(),
#     color="red",
# )

# chat = ChatTile(
#     name="* chat", chat_with=bob, title=f"Chat with {term.red('Bob')}"
# )

# messages = [
#     MessageModel(
#         from_user=alice,
#         body="don't know... let's try:",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=bob,
#         body=f"Okay that's { term.lightgreen_bold('cool') }, "
#         "but do we have markdown support?",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=alice,
#         body=term.blue_underline(
#             "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
#         ),
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=alice,
#         body="Observe",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=bob,
#         body="No way dude",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=alice,
#         body="You know we can post links here?",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=bob,
#         body="What do you want",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=alice,
#         body="Hi",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
#     MessageModel(
#         from_user=bob,
#         body="Hello",
#         date=datetime(
#             year=2022, month=3, day=21, hour=11, minute=36, second=15
#         ),
#     ),
# ]

# for i in range(0, len(messages)):
#     asyncio.run(
#         chat.add_message_to_buffer(messages[len(messages) - 1 - i])
#     )

# contacts = Tile(
#     "d contacts test test test",
# )

# signs = "qwertyuiopasdfghjklzxcvbnm1234567890!@#$%^&*()"


# monad.add(chat)
# monad.add(contacts)
# monad.add(Tile("a name"))
# monad.add(Tile("x names"))

# loop.run_until_complete(monad.render_all())
# loop.run_until_complete(header.render(term))
# loop.run_until_complete(footer.render(term))

# async def run_in_thread(task: Callable, *args: Any) -> None:
#     """Run funntion in another thread."""
#     # it kinda works I guess somehow, prolly not thread safe
#     # Run in a custom thread pool:
#     pool = concurrent.futures.ThreadPoolExecutor()
#     await loop.run_in_executor(pool, task, *args)  # noqa: FKA01

# on_resize_event = Event()

# def on_resize(*args: str) -> None:
#     """Test function for on_resize events."""
#     monad.screen_rect_change(
#         width=term.width, height=term.height - 2 - 1, x=0, y=header.height
#     )
#     header.width = term.width
#     # footer.on_resize(term)
#     loop.create_task(monad.render_all())
#     loop.create_task(header.render(term))
#     on_resize_event.set()

# loop.create_task(send_test_messages_from_bob())

# # signal handling, it kinda works
# loop.add_signal_handler(signal.SIGWINCH, on_resize)

# async def test() -> None:
#     """Test the input function."""
#     while True:
#         inp_tuple = await (footer.input_queue.get())

#         mode = inp_tuple[0]
#         inp = inp_tuple[1]

#         cmd = None
#         if mode == "layout" and inp in cmds_layout:
#             cmd = cmds_layout[inp]
#             if cmd:
#                 focus_cmds = [
#                     monad.cmd_down,
#                     monad.cmd_up,
#                     monad.cmd_left,
#                     monad.cmd_right,
#                 ]

#                 if cmd == monad.add:
#                     cmd(Tile(choice(signs) + " name"))
#                 elif cmd == monad.remove:
#                     target = monad.focused
#                     try:
#                         cmd(monad.tiles[target])
#                     except IndexError:
#                         pass
#                 else:
#                     cmd()
#                 if cmd in focus_cmds:
#                     await monad.render_focus()
#                 else:
#                     await monad.render_all()
#         elif mode == "":
#             if monad.current_tile:
#                 await monad.current_tile.consume_input(inp, term)

# loop.create_task(test())

# loop.create_task(
#     run_in_thread(footer.input, term, loop, on_resize_event)  # noqa: FKA01
# )

# loop.run_forever()