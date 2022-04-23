"""Define models of data structures used within the client."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class UserModel:
    """User model."""

    username: str
    id: str
    color: str


@dataclass
class MessageModel:
    """Message Model."""

    date: datetime
    body: str
    from_user: UserModel
    to_user: UserModel
    # embeds:     List[Any] = []
