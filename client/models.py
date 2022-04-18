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
    date:       datetime 
    body:       str
    from_user:  UserModel = None
    to_user:    UserModel = None
    #embeds:     List[Any] = []

    