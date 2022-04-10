"""Exceptions related to the CANS message API."""


class CansMessageException(Exception):
    """Abstract exception type."""

    pass


class CansDeserializationError(CansMessageException):
    """Error thrown on deserialization failure."""

    pass
