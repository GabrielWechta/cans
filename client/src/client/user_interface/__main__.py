"""For CLI usage and debugging."""
import asyncio
import hashlib

from blessed import Terminal

from ..models import MessageModel, UserModel
from ..user_interface import UserInterface

# from .view import View


async def upstream_sink(message_model: MessageModel) -> None:
    """Drop outgoing messages."""
    assert message_model


term = Terminal()
loop = asyncio.get_event_loop()

ui = UserInterface(loop, upstream_sink)

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

loop.create_task(ui.view.render_all())


async def send_test_messages_from_bob() -> None:
    """Send some stuff from bob."""
    while True:
        ui.on_new_message_received_str("test message", bob)
        await asyncio.sleep(2)


loop.create_task(send_test_messages_from_bob())

loop.run_forever()
