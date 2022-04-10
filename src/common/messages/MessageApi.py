"""Define public messaging API of the CANS application."""

from json import JSONDecodeError, JSONDecoder, JSONEncoder
from typing import Any

from common.messages.CansMessage import CansMessage
from common.messages.CansSerial import CansSerial
from common.messages.exceptions.CansDeserializationError import (
    CansDeserializationError,
)
from common.messages.exceptions.CansInternalError import CansInternalError


async def cans_recv(socket: Any) -> CansMessage:
    """Receive a CANS message from a socket.

    Ducktype the socket as client and server
    use different representations.
    """
    if not hasattr(socket, "recv"):
        raise CansInternalError("cans_recv called with an invalid object")

    serial = await socket.recv()
    return __deserialize(serial)


async def cans_send(msg: CansMessage, socket: Any) -> None:
    """Push a CANS message to a socket.

    Ducktype the socket as client and server
    use different representations.
    """
    if not hasattr(socket, "send"):
        raise CansInternalError("cans_send called with an invalid object")

    serial = __serialize(msg)
    await socket.send(serial)


def __serialize(msg: CansMessage) -> CansSerial:
    """Serialize a CANS message."""
    return JSONEncoder().encode(
        {"header": msg.header.__dict__, "payload": msg.payload}
    )


def __deserialize(serial: CansSerial) -> CansMessage:
    """Deserialize a CANS message."""
    try:
        pretender = JSONDecoder().decode(serial)
    except JSONDecodeError:
        raise CansDeserializationError("JSON deserialization failed")

    __validate_format(pretender)

    message = CansMessage()
    message.header.sender = pretender["header"]["sender"]
    message.header.receiver = pretender["header"]["receiver"]
    message.header.msg_id = pretender["header"]["msg_id"]
    message.payload = pretender["payload"]

    return message


def __validate_format(pretender: dict) -> None:
    """Validate the format of a CANS message."""
    # TODO: If this is too much overhead, simply try accessing all
    #       mandatory fields and catch KeyErrors
    try:
        # Assert at least the header is present
        if "header" not in pretender.keys():
            raise CansDeserializationError("No valid header")

        # Assert valid format header
        for header_field in pretender["header"].keys():
            if header_field not in CansMessage.CansHeader().__dict__:
                raise CansDeserializationError(
                    f"Unexpected header field: {header_field}"
                )
        for expected_field in CansMessage.CansHeader().__dict__.keys():
            if expected_field not in pretender["header"].keys():
                raise CansDeserializationError(
                    f"Header field missing: {expected_field}"
                )

        # Assert no other fields
        for field in pretender.keys():
            if field not in ["header", "payload"]:
                raise CansDeserializationError(f"Unexpected field: {field}")

    except Exception as e:
        # Translate any exception to a deserialization error
        raise CansDeserializationError(f"Unknown error: {e.args}")
