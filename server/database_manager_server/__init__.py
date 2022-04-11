"""Serverside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging


class DatabaseManager:
    """Serverside database manager."""

    def __init__(self) -> None:
        """Construct the serverside database manager."""
        self.log = logging.getLogger("cans-logger")
