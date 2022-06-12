"""
Defines various UI state machines.

Used for multi-step user inputs.
"""

from enum import Enum, auto, unique
from typing import Any, Iterable, List


class StateMachine:
    """Base state machine class."""

    def __init__(self, enum: Iterable, state: int) -> None:
        """Init the state machine."""
        self._state = state
        self.type = enum
        self._states: List[Any] = list(enum)

    @property
    def is_last(self) -> bool:
        """Check if state machine is at last state."""
        return self._state == len(self._states) - 1

    @property
    def state(self) -> Any:
        """Get current state."""
        return self._states[self._state]

    @state.setter
    def state(self, state: int) -> None:
        """Set current state."""
        if len(self._states) > state and state >= 0:
            self._state = state

    def next(self) -> Any:
        """Return and set the next state."""
        if len(self._states) > self._state + 1:
            self._state += 1
        return self._states[self._state]

    def prev(self) -> Any:
        """Return and set the previous state."""
        if self._state > 0:
            self._state -= 1
        return self._states[self._state]


@unique
class StartupState(Enum):
    """Define input states during startup phase."""

    PROMPT_USERNAME = auto()
    PROMPT_PASSWORD = auto()
    PROMPT_COLOR = auto()


@unique
class PasswordRecoveryState(Enum):
    """Define input states during password recovery."""

    PROMPT_MNEMONIC = auto()
    PROMPT_NEW_PASSWORD = auto()


if __name__ == "__main__":
    new_enum = StateMachine(StartupState, state=0)
    print(new_enum.state)
    print(new_enum.next())
    print(new_enum.next())
    print(new_enum.next())
    print(new_enum.next())
    print(new_enum.prev())
    print(new_enum.prev())
    print(new_enum.prev())
    print(new_enum.prev())
    print(new_enum.state)
    new_enum.state = 1
    print(new_enum.state)
    new_enum.state = -1
    print(new_enum.state)
    new_enum.state = 3
    print(new_enum.state)
    new_enum.state = 2
    print(new_enum.state)
