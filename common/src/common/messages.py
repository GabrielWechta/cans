"""Define CANS message formats."""

from enum import IntEnum, unique
from json import JSONDecodeError, JSONDecoder, JSONEncoder
from typing import Any, Dict, List, Optional, Union

from websockets.client import WebSocketClientProtocol
from websockets.server import WebSocketServerProtocol

from .keys import PubKey, PubKeyDigest, PublicKeysBundle

CansSerial = str


@unique
class CansMsgId(IntEnum):
    """CANS message ID."""

    USER_MESSAGE = 0
    SERVER_HELLO = 1
    PEER_LOGIN = 2
    PEER_LOGOUT = 3
    ADD_SUBSCRIPTION = 4
    REMOVE_SUBSCRIPTION = 5
    ADD_BLACKLIST = 6
    REMOVE_BLACKLIST = 7
    SHARE_CONTACTS = 8
    PEER_UNAVAILABLE = 9  # TODO: Remove this
    ACTIVE_FRIENDS = 10
    GET_KEY_BUNDLE_REQ = 11
    GET_KEY_BUNDLE_RESP = 12
    REPLENISH_ONE_TIME_KEYS_REQ = 13
    REPLENISH_ONE_TIME_KEYS_RESP = 14


class CansMessage:
    """An abstract prototype for a CANS message."""

    def __init__(self) -> None:
        """Create a CANS message."""
        self.header = self.CansHeader()
        self.payload: Any = None

    class CansHeader:
        """CANS header."""

        def __init__(self) -> None:
            """Create a CANS header."""
            self.sender: Optional[PubKeyDigest] = None
            self.receiver: Optional[PubKeyDigest] = None
            self.msg_id: CansMsgId = CansMsgId.USER_MESSAGE


class UserMessage(CansMessage):
    """User message."""

    def __init__(self, receiver: PubKeyDigest) -> None:
        """Create a CANS user message to a peer."""
        super().__init__()
        self.header.msg_id = CansMsgId.USER_MESSAGE
        self.header.receiver = receiver


class PeerUnavailable(CansMessage):
    """Peer unavailable notification."""

    def __init__(self, receiver: PubKeyDigest, peer: PubKeyDigest) -> None:
        """Create a peer unavailable notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_UNAVAILABLE
        self.header.receiver = receiver
        self.header.sender = None
        self.payload = {"peer": peer}


class ServerHello(CansMessage):
    """Dummy handshake message.

    To be replaced with actual authentication.
    """

    def __init__(
        self,
        public_key: PubKey,
        subscriptions: List[PubKeyDigest],
        identity_key: str,
        one_time_keys: Dict[str, str],
    ) -> None:
        """Create a dummy handshake message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SERVER_HELLO
        self.header.receiver = None
        self.payload = {
            "public_key": public_key,
            "subscriptions": subscriptions,
            "identity_key": identity_key,
            "one_time_keys": one_time_keys,
        }


class PeerLogin(CansMessage):
    """Peer login notification."""

    def __init__(
        self,
        receiver: PubKeyDigest,
        peer: PubKeyDigest,
        public_keys_bundle: PublicKeysBundle,
    ) -> None:
        """Create a peer login notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_LOGIN
        self.header.receiver = receiver
        self.payload = {"peer": peer, "public_keys_bundle": public_keys_bundle}


class PeerLogout(CansMessage):
    """Peer logout notification."""

    def __init__(self, receiver: PubKeyDigest, peer: PubKeyDigest) -> None:
        """Create a peer logout notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_LOGOUT
        self.header.receiver = receiver
        self.payload = {"peer": peer}


class AddSubscription(CansMessage):
    """Add subscription request."""

    def __init__(self, subscriptions: List[PubKeyDigest]) -> None:
        """Create an add subscription request."""
        super().__init__()
        self.header.msg_id = CansMsgId.ADD_SUBSCRIPTION
        self.header.receiver = None
        self.payload = {"subscriptions": subscriptions}


class RemoveSubscription(CansMessage):
    """Remove subscription request."""

    def __init__(self, subscriptions: List[PubKeyDigest]) -> None:
        """Create a remove subscription request."""
        super().__init__()
        self.header.msg_id = CansMsgId.REMOVE_SUBSCRIPTION
        self.header.receiver = None
        self.payload = {"subscriptions": subscriptions}


class AddBlacklist(CansMessage):
    """Blacklist users request."""

    def __init__(self, blacklist: List[PubKeyDigest]) -> None:
        """Create a blacklist request."""
        super().__init__()
        self.header.msg_id = CansMsgId.ADD_BLACKLIST
        self.header.receiver = None
        self.payload = {"users": blacklist}


class RemoveBlacklist(CansMessage):
    """Whitelist users request."""

    def __init__(self, whitelist: List[PubKeyDigest]) -> None:
        """Create a whitelist request."""
        super().__init__()
        self.header.msg_id = CansMsgId.REMOVE_BLACKLIST
        self.header.receiver = None
        self.payload = {"users": whitelist}


class ActiveFriends(CansMessage):
    """Notify the client during handshake who's online."""

    def __init__(
        self,
        receiver: PubKeyDigest,
        active_friends: Dict[PubKeyDigest, PublicKeysBundle],
    ) -> None:
        """Create an active friends notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.ACTIVE_FRIENDS
        self.header.receiver = receiver
        self.payload = {"friends": active_friends}


class GetKeyBundleReq(CansMessage):
    """Request peer's double-ratched key bundle."""

    def __init__(self, peer: PubKeyDigest) -> None:
        """Create a key bundle request."""
        super().__init__()
        self.header.msg_id = CansMsgId.GET_KEY_BUNDLE_REQ
        self.header.receiver = None
        self.payload = {"peer": peer}


class GetKeyBundleResp(CansMessage):
    """Send double-ratched key bundle back to the requestor."""

    def __init__(
        self, receiver: PubKeyDigest, identity_key: str, one_time_key: str
    ) -> None:
        """Create a key bundle response."""
        super().__init__()
        self.header.msg_id = CansMsgId.GET_KEY_BUNDLE_RESP
        self.header.sender = None
        self.header.receiver = receiver
        self.payload = {
            "identity_key": identity_key,
            "one_time_key": one_time_key,
        }


class ReplenishOneTimeKeysReq(CansMessage):
    """Send replenish one time keys request to the client."""

    def __init__(self, receiver: PubKeyDigest, one_time_keys_num: int) -> None:
        """Create a replenish request."""
        super().__init__()
        self.header.msg_id = CansMsgId.REPLENISH_ONE_TIME_KEYS_REQ
        self.header.sender = None
        self.header.receiver = receiver
        self.payload = {
            "one_time_keys_num": one_time_keys_num,
        }


class ReplenishOneTimeKeysResp(CansMessage):
    """Send replenish one time keys response to the server."""

    def __init__(self, one_time_keys: Dict[str, str]) -> None:
        """Create replenish response."""
        super().__init__()
        self.header.msg_id = CansMsgId.REPLENISH_ONE_TIME_KEYS_RESP
        self.header.receiver = None
        self.payload = {
            "one_time_keys": one_time_keys,
        }


class CansMessageException(Exception):
    """Abstract exception type."""

    pass


class CansDeserializationError(CansMessageException):
    """Error thrown on deserialization failure."""

    pass


async def cans_recv(
    socket: Union[WebSocketClientProtocol, WebSocketServerProtocol]
) -> CansMessage:
    """Receive a CANS message from a socket."""
    serial = str(await socket.recv())
    return __deserialize(serial)


async def cans_send(
    msg: CansMessage,
    socket: Union[WebSocketClientProtocol, WebSocketServerProtocol],
) -> None:
    """Push a CANS message to a socket."""
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
