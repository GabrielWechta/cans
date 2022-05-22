"""Clientside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging
from datetime import date
from pathlib import Path

from playhouse.sqlcipher_ext import SqlCipherDatabase

from client.database_models import (
    CansChatColor,
    CansMessageState,
    Friend,
    Message,
    Setting,
    db_proxy,
)


class DatabaseManager:
    """Clientside database manager."""

    def __init__(self, name: Path, password: str) -> None:
        """Construct the clientside database manager."""
        self.log = logging.getLogger("cans-logger")
        self._db_name = name
        self._db_pass = password

    def initialize(self) -> None:
        """Set up the connection with application's database."""
        self.db = SqlCipherDatabase(self._db_name, self._db_pass)
        db_proxy.initialize(self.db)
        self.db.create_tables([Friend, Message, Setting])

    def add_friend(
        self,
        pubkeydigest: str,
        username: str,
        chat_color: CansChatColor,
        date_added: date,
    ) -> Friend:
        """Save new friend to the database."""
        return Friend.create(
            pubkeydigest=pubkeydigest,
            username=username,
            chat_color=chat_color.value,
            date_added=date_added,
        )

    def get_all_friends(self) -> list:
        """Get a list of friends from the database."""
        return list(Friend.select())

    def save_message(
        self, state: CansMessageState, sender: str, receiver: str
    ) -> Message:
        """Save a message to the database."""
        return Message.create(
            state=state.value, sender=sender, receiver=receiver
        )

    def get_message_history_with_friend(
        self,
        pubkeydigest: str,
    ) -> tuple[list, list]:
        """Get message history with specific friend.

        Returns a tuple with two lists. First one is messages from a specific
        friend and the other contains messages sent to this friend.
        """
        friend = Friend.get(Friend.pubkeydigest == pubkeydigest)

        return list(friend.inbox), list(friend.outbox)

    def create_setting(self, option: str, value: str) -> Setting:
        """Save a new setting to the database."""
        return Setting.create(option=option, value=value)

    def update_setting(self, option: str, value: str) -> bool:
        """Update specified setting with provided value."""
        setting = Setting.get_by_id(option)
        setting.value = value
        is_successful = setting.save()
        if is_successful == 1:
            return True
        else:
            return False
