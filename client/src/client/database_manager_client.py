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

    def __init__(self, name: str) -> None:
        """Construct the clientside database manager."""
        self.log = logging.getLogger("cans-logger")
        self._db_name = str(name)

    def open(self, passphrase: str = "") -> Optional[str]:
        """Set up the connection with application's database."""
        self.db = SqlCipherDatabase(self._db_name, passphrase=passphrase)
        try:
            db_proxy.initialize(self.db)
            self.db.create_tables([Friend, Message, Setting])
        except peewee.DatabaseError as e:
            if str(e) == "file is encrypted or is not a database":
                return "Wrong password"
            else:
                return str(e)
        self.log.debug("Successfully initialized database connection.")
        return None

    def close(self) -> None:
        """Close the database."""
        if hasattr(self, "db"):
            self.db.close()

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
            except peewee.IntegrityError as e:
                try:
                    self.log.error(
                        f"Failed to save {friend.username} to the database, "
                        + f"because {str(e)}."
                    )
                    return Friend.get(id=friend.id)
                except peewee.DoesNotExist:
                    self.log.error(
                        f"Couldn't fetch {friend.username} from database."
                    )
                    return None
        elif all(key in kwargs for key in ("id", "username", "color")):
            try:
                return Friend.create(
                    date_added=date_added,
                    **kwargs,
                )
            except peewee.IntegrityError as e1:
                try:
                    self.log.error(
                        f"Failed to save {kwargs['username']} to the database,"
                        + f" because {str(e1)}."
                    )
                    return Friend.get(id=kwargs["id"])
                except peewee.DoesNotExist:
                    self.log.error(
                        f"Couldn't fetch {kwargs['username']} from the "
                        + "database."
                    )
                    return None
        else:
            self.log.error("Not enough parameters to save a new friend.")
            return None

    def get_friend(
        self,
        id: str,
    ) -> Optional[Friend]:
        """Read this friend data from the database."""
        try:
            return Friend.get_by_id(pk=id)
        except peewee.DoesNotExist:
            self.log.error(f"No friend with {id} key in database.")
            return None

    def get_all_friends(self) -> list:
        """Get a list of friends from the database."""
        return list(
            Friend.select().where(
                (Friend.id != "myself") & (Friend.id != "system")
            )
        )

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
            except peewee.IntegrityError as e:
                self.log.error(
                    f"Failed to update {friend.username}'s data, because "
                    + f"{str(e)}."
                )
                return False
        elif kwargs and id:
            try:
                is_successful = Friend.set_by_id(key=id, value=kwargs)
            except peewee.IntegrityError as e1:
                self.log.error(
                    f"Failed to update friend with {id} key, because "
                    + f"{str(e1)}."
                )
                return False

        if is_successful == 1:
            return True
        else:
            self.log.error("Failed to update Friend data.")
            return False

    def remove_friend(self, id: str) -> bool:
        """Delete this friend's data."""
        try:
            is_successful = Friend.delete_by_id(pk=id)

            if is_successful == 1:
                return True
            else:
                self.log.error(f"Failed to delete friend with {id} key.")
                return False
        except peewee.IntegrityError as e:
            self.log.error(
                f"Failed to delete friend with {id} key, because {str(e)}."
            )
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
            except peewee.IntegrityError as e:
                try:
                    self.log.error(
                        f"Unable to save message {message.id} to database, "
                        + f"because {str(e)}."
                    )
                    return Message.get(id=message.id)
                except peewee.DoesNotExist:
                    self.log.error(
                        f"Couldn't fetch message {message.id} "
                        + "from the database."
                    )
                    return None
        elif all(key in kwargs for key in ("body", "from_user", "to_user")):
            try:
                return Message.create(
                    date=date,
                    state=state,
                    **kwargs,
                )
            except peewee.IntegrityError as e1:
                try:
                    if "id" in kwargs:
                        self.log.error(
                            f"Unable to save message {kwargs['id']} to "
                            + f"database, because {str(e1)}."
                        )
                        return Message.get(id=kwargs["id"])
                    else:
                        self.log.error(
                            f"Unable to save {kwargs['body']} to database, "
                            + f"because {str(e1)}."
                        )
                        return None
                except peewee.DoesNotExist:
                    self.log.error(
                        f"Unable to fetch message {kwargs['id']} "
                        + "from database."
                    )
                    return None
        else:
            return None

    def get_message(self, id: str) -> Optional[Message]:
        """Read this message data from the database."""
        try:
            return Message.get_by_id(pk=id)
        except peewee.DoesNotExist:
            self.log.error(f"Message {id} doesn't exist in database.")
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
            self.log.error(f"There's no friend with {id} key in the database.")
            return []

        return list(
            Message.select()
            .where((Message.from_user == friend) | (Message.to_user == friend))
            .order_by(Message.date)
        )

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
            except peewee.IntegrityError as e:
                self.log.error(
                    f"Failed to update message {message.id} in database, "
                    + f"because {str(e)}."
                )
                return False
        elif id:
            try:
                is_successful = Message.set_by_id(
                    key=id, value={**kwargs, "date": date, "state": state}
                )
            except peewee.IntegrityError as e1:
                self.log.error(
                    f"Failed to update message {id} in database, "
                    + f"because {str(e1)}."
                )
                return False

        if is_successful == 1:
            return True
        else:
            self.log.error("Failed to update this message in database.")
            return False

    def delete_message(self, id: str) -> bool:
        """Delete this message data."""
        try:
            is_successful = Message.delete_by_id(pk=id)

            if is_successful == 1:
                return True
            else:
                self.log.error(f"Failed to delete message {id} from database.")
                return False
        except peewee.IntegrityError as e:
            self.log.error(
                f"Failed to delete message {id} from database, "
                + f"because {str(e)}."
            )
            return False

    def delete_message_history_with_friend(self, id: str) -> bool:
        """Delete message history with this friend."""
        try:
            friend = Friend.get_by_id(pk=id)
        except peewee.DoesNotExist:
            self.log.error(f"There's no friend with {id} key in the database.")
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
                self.log.debug(
                    f"No message history with {id} or error during deletion."
                )
                return False
        except peewee.IntegrityError as e:
            self.log.error(
                f"Failed to delete message history with {id}, because "
                + f"{str(e)}."
            )
            return False

    def create_setting(self, option: str, value: str) -> Optional[Setting]:
        """Save a new setting to the database."""
        try:
            return Setting.create(option=option, value=value)
        except peewee.IntegrityError as e:
            try:
                self.log.error(
                    f"Unable to save setting {option} "
                    + f"to {value} in the database, because {str(e)}."
                )
                return Setting.get_by_id(pk=option)
            except peewee.DoesNotExist:
                self.log.error(
                    "Unable to fetch setting {option} from database."
                )
                return None

    def get_setting(self, option: str) -> Optional[Setting]:
        """Read a setting from the database."""
        try:
            return Setting.get_by_id(pk=option)
        except peewee.DoesNotExist:
            self.log.error(f"Setting {option} doesn't exist in the database.")
            return None

    def get_all_settings(self) -> list:
        """Get a list of settings from the database."""
        return list(Setting.select())

    def update_setting(self, option: str, value: str) -> bool:
        """Update specified setting with provided value."""
        try:
            is_successful = Setting.set_by_id(
                key=option, value={"value": value}
            )
            if is_successful == 1:
                return True
            else:
                self.log.error(
                    f"Updating setting {option} in the database failed."
                )
                return False
        except peewee.IntegrityError as e:
            self.log.error(
                f"Updating setting {option} in the database failed, "
                + f"because {str(e)}."
            )
            return False

    def delete_setting(self, option: str) -> bool:
        """Remove this setting from the database."""
        try:
            is_successful = Setting.delete_by_id(pk=option)

            if is_successful == 1:
                return True
            else:
                self.log.error(
                    f"Deleting setting {option} in the database failed."
                )
                return False
        except peewee.IntegrityError as e:
            self.log.error(
                f"Deleting setting {option} in the database failed, "
                + f"because {str(e)}."
            )
            return False
