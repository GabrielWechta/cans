"""Define models of data structures used within the client"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Any


@dataclass
class UserModel:
    username:   str
    id:         str
    color:      str

@dataclass
class MessageModel:
    from_user:  UserModel
    to_user:    UserModel
    date:       datetime
    body:       str
    embeds:     List[Any]

    