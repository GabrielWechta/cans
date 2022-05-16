"""Serverside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging
from typing import Dict, Set


class DatabaseManager:
    """Serverside database manager."""

    def __init__(self) -> None:
        """Construct the serverside database manager."""
        self.log = logging.getLogger("cans-logger")
        self.subscribers_of: Dict[str, Set[str]] = {}

    async def get_subscribers_of(self, target: str) -> Set[str]:
        """Fetch a list of subscribers."""
        # TODO: Use the database
        if target in self.subscribers_of.keys():
            return self.subscribers_of[target]
        else:
            return set()

    async def add_subscriber_of(self, target: str, subscriber: str) -> None:
        """Store a subscription in the database."""
        # TODO: Use the database
        if target in self.subscribers_of.keys():
            self.subscribers_of[target].add(subscriber)
        else:
            self.subscribers_of[target] = {subscriber}
