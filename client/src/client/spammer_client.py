"""Spammer client service."""
import asyncio
import os
import sys
from random import choice, randrange

from olm import Account

from common.keys import digest_key, generate_keys

from .session_manager_client import SessionManager, ShareFriend

messages = [
    "Beautiful is better than ugly.",
    "Explicit is better than implicit.",
    "Simple is better than complex.",
    "Complex is better than complicated.",
    "Flat is better than nested.",
    "Sparse is better than dense.",
    "Readability counts.",
    "Special cases aren't special enough to break the rules.",
    "Although practicality beats purity.",
    "Errors should never pass silently.",
    "Unless explicitly silenced.",
    "In the face of ambiguity, refuse the temptation to guess.",
    "There should be one-- and preferably only one --obvious way to do it.",
    "Although that way may not be obvious at first unless you're Dutch.",
    "Now is better than never.",
    "Although never is often better than right now.",
    "If the implementation is hard to explain, it's a bad idea.",
    "If the implementation is easy to explain, it may be a good idea.",
    "Namespaces are one honking great idea -- let's do more of those!",
]


class SpammerClient:
    """Spammer client service."""

    def __init__(self) -> None:
        """Run a spammer client."""
        self.server_hostname = os.environ["CANS_SERVER_HOSTNAME"]
        self.server_port = os.environ["CANS_PORT"]
        self.certpath = os.environ["CANS_SELF_SIGNED_CERT_PATH"]

        self.event_loop = asyncio.get_event_loop()

        account = Account()

        private_key, public_key = generate_keys()
        print(public_key)
        print(private_key)
        print("Key digest: \n" + digest_key(public_key))

        self.session_manager = SessionManager(
            keys=(private_key, public_key),
            account=account,
        )

    def run(self, peer_id: str) -> None:
        """Run the echo client service."""
        # Connect to the server
        self.event_loop.run_until_complete(
            asyncio.gather(  # noqa: FKA01
                self.session_manager.connect(
                    url=f"wss://{self.server_hostname}:{self.server_port}",
                    certpath=self.certpath,
                    friends=set(),
                ),
                self._spam_service(peer_id),
                self._cplane_sink(),
                self._uplane_sink(),
            )
        )

    async def _spam_service(self, peer_id: str) -> None:
        """Implement the spamming service."""
        await self.session_manager.add_friend(peer_id)
        while True:
            message, cookie = self.session_manager.user_message_to(
                peer=peer_id, payload=choice(messages)
            )
            await self.session_manager.send_message(message)
            # await asyncio.sleep(5)
            share_friend_message = ShareFriend(
                receiver=peer_id,
                shared_friend=randrange(2**24, 2**31)
                .to_bytes(4, "little")
                .hex(),
                local_name="test" + str(randrange(0, 2**16)),
            )

            await self.session_manager.send_message(share_friend_message)
            await asyncio.sleep(5)

    async def _cplane_sink(self) -> None:
        """Drop control messages received by the spammer service."""
        while True:
            message = await self.session_manager.receive_system_message()
            message = message

    async def _uplane_sink(self) -> None:
        """Drop user messages received by the spammer service."""
        while True:
            message = await self.session_manager.receive_user_message()
            message = message


if __name__ == "__main__":
    if len(sys.argv) > 1:
        peer_id = sys.argv[1]
    else:
        peer_id = ""
    print("Peer id: " + peer_id)
    client = SpammerClient()
    client.run(peer_id)
