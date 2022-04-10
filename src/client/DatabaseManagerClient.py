"""Clientside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging


class DatabaseManagerClient:
    """Clientside database manager."""

    def __init__(self) -> None:
        """Construct the clientside database manager."""
        self.log = logging.getLogger("cans-logger")
