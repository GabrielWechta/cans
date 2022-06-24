"""Application-specific WebSocket status codes."""

from enum import IntEnum, unique


@unique
class CansStatusCode(IntEnum):
    """Connection closed status codes."""

    AUTH_FAILURE = 3000
    EXCEPTION_RAISED = 3001
    MALFORMED_MESSAGE = 3002
