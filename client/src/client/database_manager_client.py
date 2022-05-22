"""Clientside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging
from datetime import date
from pathlib import Path

from playhouse.sqlcipher_ext import SqlCipherDatabase

from client.database_models import Friend, Message, Setting, db_proxy


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
        chat_color: str,
        date_added: date,
    ) -> Friend:
        """Save new friend to database."""
        return Friend.create(
            pubkeydigest=pubkeydigest,
            username=username,
            chat_color=chat_color,
            date_added=date_added,
        )
