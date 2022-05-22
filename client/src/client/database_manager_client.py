"""Clientside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging
from datetime import datetime
from typing import List, Optional

import peewee
from playhouse.sqlcipher_ext import SqlCipherDatabase

from .models import CansMessageState, Friend, Message, Setting, db_proxy


class DatabaseManager:
    """Clientside database manager."""

    def __init__(self, name: str, password: str) -> None:
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
        id: str,
        username: str,
        color: str,
        date_added: datetime,
    ) -> Optional[Friend]:
        """Save new friend to the database."""
        try:
            return Friend.create(
                id=id,
                username=username,
                color=color,
                date_added=date_added,
            )
        except peewee.IntegrityError:
            try:
                return Friend.get(id=id)
            except peewee.DoesNotExist:
                return None

    def get_all_friends(self) -> list:
        """Get a list of friends from the database."""
        try:
            return list(Friend.select())
        except peewee.DoesNotExist:
            return []

    def save_message(
        self,
        body: str,
        date: datetime,
        state: CansMessageState,
        from_user: str,
        to_user: str,
    ) -> Optional[Message]:
        """Save a message to the database.

        Sender and receiver are identified by their pubkeydigest.
        """
        try:
            return Message.create(
                body=body,
                date=date,
                state=state.value,
                from_user=from_user,
                to_user=to_user,
            )
        except peewee.IntegrityError:
            return None

    def get_message_history_with_friend(
        self,
        id: str,
    ) -> List[Message]:
        """Get message history with specific friend.

        Returns a tuple with two lists. First one is messages from a specific
        friend and the other contains messages sent to this friend.

        TODO: we only need messages in and out, this doesnt make sense
        """
        try:
            friend = Friend.get(Friend.id == id)
        except peewee.DoesNotExist:
            return []
        # return list(friend.inbox), list(friend.outbox)
        try:
            return list(
                Message.select()
                .where(
                    (Message.from_user == friend) | (Message.to_user == friend)
                )
                .order_by(Message.date)
            )
        except peewee.DoesNotExist:
            return []

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
