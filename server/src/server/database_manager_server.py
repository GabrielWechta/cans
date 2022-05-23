"""Serverside database manager.

Expose an API for interacting with the database and
fetching/committing application-specific data.
"""
import logging
import os
from typing import Dict, List, Optional, Set

import peewee
from playhouse.sqlite_ext import SqliteExtDatabase

from .database_models import Subscribtion, User, db_proxy


class DatabaseManager:
    """Serverside database manager."""

    def __init__(self) -> None:
        """Construct the serverside database manager."""
        self.log = logging.getLogger("cans-logger")
        self._db_name = os.environ["CANS_SERVER_DB_NAME"]
        self._db_pass = os.environ["CANS_SERVER_DB_PASSWORD"]

        self.db = SqliteExtDatabase(self._db_name, self._db_pass)
        db_proxy.initialize(self.db)

        self.db.create_tables([User, Subscribtion])

        self.subscribers_of: Dict[str, Set[str]] = {}

    async def get_subscribers_of(self, target: str) -> List[str]:
        """Fetch a list of subscribers."""
        # TODO: Use the database
        try:
            user = User.get(User.key == target)
        except peewee.DoesNotExist:
            user = await self.add_user(target)

        try:
            subscriptions = [
                row.subscriber_id
                for row in Subscribtion.select().where(
                    Subscribtion.subscribed == user
                )
            ]
            return subscriptions  # type: ignore
        except peewee.DoesNotExist:
            return []

    async def add_user(self, key: str) -> Optional[User]:
        """Add user to user list."""
        try:
            user = User.create(
                key=key,
            )
        except peewee.IntegrityError:
            user = None
        return user

    async def add_subscriber_of(
        self, target: str, subscriber: str
    ) -> Optional[Subscribtion]:
        """Store a subscription in the database."""
        try:
            subscriber_db = User.get(User.key == subscriber)
        except peewee.DoesNotExist:
            subscriber_db = await self.add_user(subscriber)

        try:
            subscribed_db = User.get(User.key == target)
        except peewee.DoesNotExist:
            subscribed_db = await self.add_user(target)

        try:
            subscription = Subscribtion.create(
                subscriber=subscriber_db,
                subscribed=subscribed_db,
            )
        except peewee.IntegrityError:
            subscription = None

        return subscription

    async def remove_subscriber_of(self, target: str, subscriber: str) -> None:
        """Remove a subscription from the database."""
        try:
            subscription = Subscribtion.delete().where(
                Subscribtion.subscriber == subscriber,
                Subscribtion.subscribed == target,
            )
            subscription.execute()
        except peewee.DoesNotExist:
            return
