"""Serverside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""

import logging
from typing import Dict, Set

from common.keys import PubKeyDigest


class DatabaseManager:
    """Serverside database manager."""

    def __init__(self) -> None:
        """Construct the serverside database manager."""
        self.log = logging.getLogger("cans-logger")
        self.subscribers_of: Dict[PubKeyDigest, Set[PubKeyDigest]] = {}

    async def get_subscribers_of(
        self, target: PubKeyDigest
    ) -> Set[PubKeyDigest]:
        """Fetch a list of subscribers."""
        # TODO: Use the database
        if target in self.subscribers_of.keys():
            return self.subscribers_of[target]
        else:
            return set()

    async def add_subscriber_of(
        self, target: PubKeyDigest, subscriber: PubKeyDigest
    ) -> None:
        """Store a subscription in the database."""
        # TODO: Use the database
        if target in self.subscribers_of.keys():
            self.subscribers_of[target].add(subscriber)
        else:
            self.subscribers_of[target] = {subscriber}
