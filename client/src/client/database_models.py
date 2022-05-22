"""Define models of tables and data used by the database."""

from enum import IntEnum, auto, unique
from typing import Type

import peewee

db_proxy = peewee.Proxy()


def make_table_name(model_class: Type[peewee.Model]) -> str:
    """Create a naming convention for the tables."""
    model_name = model_class.__name__
    return model_name.lower() + "s"


@unique
class CansMessageState(IntEnum):
    """State of a cans message in the database."""

    DELIVERED = auto()
    NOT_DELIVERED = auto()


@unique
class CansChatColor(IntEnum):
    """Available chat colors."""

    # TODO add more colors
    RED = auto()
    GREEN = auto()
    BLUE = auto()


class BaseModel(peewee.Model):
    """A base model class.

    Establishes the connection with the database for the table models and
    specifies the naming convention.
    """

    class Meta:
        """Class defining key parameters of a table model."""

        db = db_proxy
        table_function = make_table_name


class Friend(BaseModel):
    """Model for the database table friends."""

    pubkeydigest = peewee.CharField(primary_key=True)
    username = peewee.CharField()
    chat_color = peewee.IntegerField()
    date_added = peewee.DateField()


class Message(BaseModel):
    """Model for the database table messages."""

    id = peewee.AutoField()
    state = peewee.IntegerField()
    sender = peewee.ForeignKeyField(Friend, backref="inbox", lazy_load=False)
    receiver = peewee.ForeignKeyField(
        Friend, backref="outbox", lazy_load=False
    )


class Setting(BaseModel):
    """Model for the database table settings."""

    option = peewee.CharField(primary_key=True)
    value = peewee.CharField()
