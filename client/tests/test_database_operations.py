"""Database operations tests."""

from datetime import datetime
from pathlib import Path

import pytest

from client.database_manager_client import DatabaseManager
from client.models import CansMessageState, Friend, Message


@pytest.fixture()
def database():
    """Define test.db for test purposes.

    Usable one time so delete it before running tests.
    """
    db = DatabaseManager(
        name=Path("test.db"),
        password="SafeAndSecurePassword2137",
        username="Bob:D",
        color="red",
    )
    return db


@pytest.fixture()
def alice(database):
    """Set up Alice. A Friend for the tests."""
    database.initialize()
    return database.add_friend(
        id="Alice", username="AliceXD", color="blue", date_added=datetime.now()
    )


@pytest.fixture()
def bob():
    """Set up Bob. Ourselves for the tests."""
    return Friend(id="Bob", username="Bob:D", color="red")


@pytest.fixture()
def bobby():
    """Set up Bobby. Bob's multiaccount to add and delete later."""
    return Friend(id="Bobby", username="LilBob", color="yellow")


def test_add_friend(database, bobby):
    """Test adding friend to database."""
    database.initialize()
    friend_inserted = database.add_friend(
        id="test_key",
        username="test_user",
        color="red",
    )
    friend_model = database.add_friend(friend=bobby)
    friend_returned = database.get_friend(id=friend_inserted.id)

    assert friend_inserted.id == friend_returned.id
    assert friend_inserted.username == friend_returned.username
    assert friend_inserted.color == friend_returned.color
    assert friend_inserted.date_added == friend_returned.date_added
    assert friend_model.username == bobby.username


def test_get_friend(database, alice, bobby):
    """Test fetching friend data from database."""
    test_existing = database.get_friend(id=alice.id)
    test_nonexisting = database.get_friend(id="Bob")
    test_all = database.get_all_friends()

    assert test_existing.username == alice.username
    assert test_nonexisting is None
    assert alice in test_all
    assert bobby in test_all


def test_update_friend(database, alice):
    """Test updating a friend in the database."""
    test_correct = database.update_friend(id=alice.id, color="azure")
    test_check = database.get_friend(id=alice.id)
    test_wrong = database.update_friend(id="Bob", color="green")

    assert test_correct and test_check.color == "azure"
    assert not test_wrong


def test_delete_friend(database, bobby):
    """Test deleting a friend from the database."""
    test_bobby = database.remove_friend(id=bobby.id)
    test_check = database.get_friend(id=bobby.id)
    test_bad = database.remove_friend(id="Bob")

    assert test_bobby and test_check is None
    assert not test_bad


def test_message_history(database, alice, bob):
    """Test saving messages and getting the message history."""
    message_in = database.save_message(
        body="Hello, Bob",
        from_user="Alice",
        to_user="Bob",
    )

    message_out_model = Message(
        body="Hello, Alice.",
        from_user=bob,
        to_user=alice,
    )

    message_out = database.save_message(
        message=message_out_model,
        state=CansMessageState.DELIVERED,
    )

    message_out_read = database.get_message(id=message_out_model.id)

    inbox = database.get_message_history_with_friend(id="Alice")

    assert inbox[0].body == message_in.body
    assert inbox[1].body == message_out.body
    assert inbox[0].date == message_in.date
    assert inbox[1].date == message_out_model.date
    assert message_out_read.to_user == message_out_model.to_user


def test_message_update(database, alice, bob):
    """Test updating the message in database."""
    message_model = Message(
        body="Hello, Alice.",
        from_user=bob,
        to_user=alice,
    )

    database.save_message(
        message=message_model,
        state=CansMessageState.DELIVERED,
    )

    update_state = database.update_message(
        id=message_model.id, state=CansMessageState.NOT_DELIVERED
    )

    message_state = database.get_message(id=message_model.id)

    update_body = database.update_message(
        id=message_model.id, body="Alice, you stink!"
    )

    message_body = database.get_message(id=message_model.id)

    update_bad = database.update_message(id=bob.id, body="Alice, you stink!")

    assert (
        update_state or message_state.state == CansMessageState.NOT_DELIVERED
    )
    assert update_body and message_body.body == "Alice, you stink!"
    assert not update_bad


def test_delete_message(database, alice, bob):
    """Test deleting a message from database."""
    message_model = Message(
        body="Very embarassing stuff.",
        from_user=bob,
        to_user=alice,
    )

    database.save_message(
        message=message_model,
        state=CansMessageState.DELIVERED,
    )

    test_correct = database.delete_message(id=message_model.id)
    test_check = database.get_message(id=message_model.id)
    test_bad = database.delete_message(id=message_model.id)
    test_all = database.delete_message_history_with_friend(id=alice.id)
    test_all_check = database.delete_message_history_with_friend(id=alice.id)

    assert test_correct and test_check is None
    assert not test_bad
    assert test_all
    assert not test_all_check
