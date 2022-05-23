"""Models for serverside database."""
from typing import Type

import peewee

db_proxy = peewee.Proxy()


def make_table_name(model_class: Type[peewee.Model]) -> str:
    """Create a naming convention for the tables."""
    model_name = model_class.__name__
    return model_name.lower() + "s"


class BaseModel(peewee.Model):
    """Base model."""

    class Meta:
        """Meta class for base model."""

        database = db_proxy
        table_function = make_table_name


class User(BaseModel):
    """User model."""

    key = peewee.CharField(primary_key=True)


class Subscribtion(BaseModel):
    """Subscribtion model."""

    id = peewee.AutoField(primary_key=True)
    subscriber = peewee.ForeignKeyField(User)
    subscribed = peewee.ForeignKeyField(User)

    class Meta:
        """Meta class for user."""

        indexes = {
            (("subscriber", "subscribed"), True),
        }
