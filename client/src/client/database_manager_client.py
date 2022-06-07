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
        self._db_name = str(name)
        self._db_pass = password

    def initialize(self) -> None:
        """Set up the connection with application's database."""
        self.db = SqlCipherDatabase(self._db_name, passphrase=self._db_pass)
        db_proxy.initialize(self.db)
        self.db.create_tables([Friend, Message, Setting])

    def add_friend(
        self,
        friend: Friend = None,
        date_added: datetime = None,
        **kwargs: str,
    ) -> Optional[Friend]:
        """Save new friend to the database."""
        if date_added is None:
            date_added = datetime.now()
        if friend is not None:
            try:
                return Friend.create(
                    id=friend.id,
                    username=friend.username,
                    color=friend.color,
                    date_added=friend.date_added,
                )
            except peewee.IntegrityError:
                try:
                    return Friend.get(id=friend.id)
                except peewee.DoesNotExist:
                    return None
        elif all(key in kwargs for key in ("id", "username", "color")):
            try:
                return Friend.create(
                    date_added=date_added,
                    **kwargs,
                )
            except peewee.IntegrityError:
                try:
                    return Friend.get(id=kwargs["id"])
                except peewee.DoesNotExist:
                    return None
        else:
            return None

    def get_friend(
        self,
        id: str,
    ) -> Optional[Friend]:
        """Read this friend data from the database."""
        try:
            return Friend.get_by_id(pk=id)
        except peewee.DoesNotExist:
            return None

    def get_all_friends(self) -> list:
        """Get a list of friends from the database."""
        try:
            return list(
                Friend.select().where(
                    (Friend.id != "myself") & (Friend.id != "system")
                )
            )
        except peewee.DoesNotExist:
            return []

    def update_friend(
        self,
        friend: Friend = None,
        id: str = "",
        **kwargs: str,
    ) -> bool:
        """Update data of this friend."""
        is_successful = 0
        if friend is not None:
            try:
                is_successful = Friend.set_by_id(
                    key=friend.id,
                    value={"username": friend.username, "color": friend.color},
                )
            except peewee.IntegrityError:
                return False
        elif kwargs and id:
            try:
                is_successful = Friend.set_by_id(key=id, value=kwargs)
            except peewee.IntegrityError:
                return False

        if is_successful == 1:
            return True
        else:
            return False

    def remove_friend(self, id: str) -> bool:
        """Delete this friend's data."""
        try:
            is_successful = Friend.delete_by_id(pk=id)

            if is_successful == 1:
                return True
            else:
                return False
        except peewee.IntegrityError:
            return False

    def save_message(
        self,
        message: Message = None,
        state: CansMessageState = CansMessageState.DELIVERED,
        date: datetime = None,
        **kwargs: str,
    ) -> Optional[Message]:
        """Save a message to the database.

        Sender and receiver are identified by their pubkeydigest.
        """
        if date is None:
            date = datetime.now()
        if message is not None:
            try:
                return Message.create(
                    id=message.id,
                    body=message.body,
                    date=message.date,
                    state=state,
                    from_user=message.from_user.id,
                    to_user=message.to_user.id,
                )
            except peewee.IntegrityError:
                try:
                    return Message.get(id=message.id)
                except peewee.DoesNotExist:
                    return None
        elif all(key in kwargs for key in ("body", "from_user", "to_user")):
            try:
                return Message.create(
                    date=date,
                    state=state,
                    **kwargs,
                )
            except peewee.IntegrityError:
                try:
                    if "id" in kwargs:
                        return Message.get(id=kwargs["id"])
                    else:
                        return None
                except peewee.DoesNotExist:
                    return None
        else:
            return None

    def get_message(self, id: str) -> Optional[Message]:
        """Read this message data from the database."""
        try:
            return Message.get_by_id(pk=id)
        except peewee.DoesNotExist:
            return None

    def get_message_history_with_friend(
        self,
        id: str,
    ) -> List[Message]:
        """Get message history with specific friend.

        Returns a list of the messages exchanged with that friend.
        """
        try:
            friend = Friend.get(Friend.id == id)
        except peewee.DoesNotExist:
            return []

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

    def update_message(
        self,
        message: Message = None,
        state: CansMessageState = CansMessageState.DELIVERED,
        date: datetime = None,
        id: str = "",
        **kwargs: str,
    ) -> bool:
        """Update the data of this message."""
        is_successful = 0
        if date is None:
            date = datetime.now()
        if message is not None:
            try:
                is_successful = Message.set_by_id(
                    key=message.id,
                    value={
                        "body": message.body,
                        "date": date,
                        "state": state,
                        "from_user": message.from_user,
                        "to_user": message.to_user,
                    },
                )
            except peewee.IntegrityError:
                return False
        elif id:
            try:
                is_successful = Message.set_by_id(
                    key=id, value={**kwargs, "date": date, "state": state}
                )
            except peewee.IntegrityError:
                return False

        if is_successful == 1:
            return True
        else:
            return False

    def delete_message(self, id: str) -> bool:
        """Delete this message data."""
        try:
            is_successful = Message.delete_by_id(pk=id)

            if is_successful == 1:
                return True
            else:
                return False
        except peewee.IntegrityError:
            return False

    def delete_message_history_with_friend(self, id: str) -> bool:
        """Delete message history with this friend."""
        try:
            friend = Friend.get_by_id(pk=id)
        except peewee.DoesNotExist:
            return True

        try:
            is_successful = (
                Message.delete()
                .where(
                    (Message.from_user == friend) | (Message.to_user == friend)
                )
                .execute()
            )

            if is_successful > 0:
                return True
            else:
                return False
        except peewee.IntegrityError:
            return False

    def create_setting(self, option: str, value: str) -> Optional[Setting]:
        """Save a new setting to the database."""
        try:
            return Setting.create(option=option, value=value)
        except peewee.IntegrityError:
            try:
                return Setting.get_by_id(pk=option)
            except peewee.DoesNotExist:
                return None

    def get_setting(self, option: str) -> Optional[Setting]:
        """Read a setting from the database."""
        try:
            return Setting.get_by_id(pk=option)
        except peewee.DoesNotExist:
            return None

    def get_all_settings(self) -> list:
        """Get a list of settings from the database."""
        try:
            return list(Setting.select())
        except peewee.DoesNotExist:
            return []

    def update_setting(self, option: str, value: str) -> bool:
        """Update specified setting with provided value."""
        try:
            is_successful = Setting.set_by_id(
                key=option, value={"value": value}
            )
            if is_successful == 1:
                return True
            else:
                return False
        except peewee.IntegrityError:
            return False

    def delete_setting(self, option: str) -> bool:
        """Remove this setting from the database."""
        try:
            is_successful = Setting.delete_by_id(pk=option)

            if is_successful == 1:
                return True
            else:
                return False
        except peewee.IntegrityError:
            return False
