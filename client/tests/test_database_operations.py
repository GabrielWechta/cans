"""Database operations tests."""

from datetime import datetime
from pathlib import Path

import pytest

from client.database_manager_client import DatabaseManager
from client.models import CansMessageState


@pytest.fixture()
def database():
    """Define test.db for test purposes.

    Usable one time so delete it before running tests.
    """
    db = DatabaseManager(Path("test.db"), "SafeAndSecurePassword2137")
    return db


def test_add_friend(database):
    """Test adding friend feature and reading friend data from database."""
    database.initialize()
    friend_inserted = database.add_friend(
        id="test_key",
        username="test_user",
        color="red",
        date_added=datetime.now(),
    )
    friend_returned = database.get_all_friends()[0]

    assert friend_inserted.id == friend_returned.id
    assert friend_inserted.username == friend_returned.username
    assert friend_inserted.color == friend_returned.color
    assert friend_inserted.date_added == friend_returned.date_added


def test_message_history(database):
    """Test saving messages and getting the message history."""
    database.initialize()
    database.add_friend(
        id="Alice", username="AliceXD", color="blue", date_added=datetime.now()
    )
    message_in = database.save_message(
        body="Hello, Bob",
        date=datetime.now(),
        state=CansMessageState.DELIVERED,
        from_user="Alice",
        to_user="Bob",
    )
    message_out = database.save_message(
        body="Hello, Alice",
        date=datetime.now(),
        state=CansMessageState.DELIVERED,
        from_user="Bob",
        to_user="Alice",
    )

    inbox, outbox = database.get_message_history_with_friend("Alice")

    assert inbox[0].body == message_in.body
    assert outbox[0].body == message_out.body
