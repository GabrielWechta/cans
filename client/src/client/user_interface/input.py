"""User input structures."""
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Union


class InputMode(IntEnum):
    """Enum defining input modes."""

    NORMAL = auto()
    LAYOUT = auto()
    COMMAND = auto()
    EXIT = auto()


@dataclass
class InputMess:
    """Input message class for UI."""

    mode: InputMode
    text: Union[str, tuple]
