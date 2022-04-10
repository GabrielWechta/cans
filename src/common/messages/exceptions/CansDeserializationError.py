"""Error thrown on deserialization failure."""

from common.messages.exceptions.CansMessageException import (
    CansMessageException,
)


class CansDeserializationError(CansMessageException):
    """Error thrown on deserialization failure."""

    pass
