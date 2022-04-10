"""Exceptions related to the CANS server."""


class CansServerException(Exception):
    """Generic abstract type for exceptions related to the CANS server."""

    pass


class CansServerAuthFailed(CansServerException):
    """Error thrown on authentication failure."""

    pass
