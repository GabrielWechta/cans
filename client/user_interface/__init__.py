"""CANS application UI."""
from blessed import Terminal


class UserInterface:
    """CANS application UI."""

    term: Terminal
    """Blessed Terminal object used to work with system's Terminal Emulator"""

    def __init__(self) -> None:
        """Instantiate a UI."""
        self.term = Terminal()
        pass

    def say_hello(self) -> None:
        """Says fucking hello."""
        print("hello 2")
