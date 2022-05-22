"""Clientside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher


class DatabaseManager:
    """Clientside database manager."""

    def __init__(self, name: Path, password: str) -> None:
        """Construct the clientside database manager."""
        self.log = logging.getLogger("cans-logger")
        self._db_name = name
        self.db_pass = password
        self._connect()

    def _connect(self) -> None:
        """Set up the connection with application's database."""
        self.conn = sqlcipher.connect(self._db_name.as_posix())
        self.cursor = self.conn.cursor()
        self.cursor.execute(f"PRAGMA key='{self.db_pass}'")
