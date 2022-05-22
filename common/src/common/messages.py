"""Define CANS message formats."""

from enum import IntEnum, auto, unique
from json import JSONDecodeError, JSONDecoder, JSONEncoder
from typing import Any, Dict, List, Optional, Union

from websockets.client import WebSocketClientProtocol
from websockets.server import WebSocketServerProtocol

from .keys import PublicKeysBundle

CansSerial = str

CANS_PEER_HANDSHAKE_MAGIC = "PeerHandshakeMagic"


@unique
class CansMsgId(IntEnum):
    """CANS message ID."""

    # User traffic
    SESSION_ESTABLISHED = auto()
    USER_MESSAGE = auto()
    PEER_HELLO = auto()
    SHARE_CONTACTS = auto()

    # Client-server handshake
    SCHNORR_COMMIT = auto()
    SCHNORR_CHALLENGE = auto()
    SCHNORR_RESPONSE = auto()

    SERVER_HELLO = auto()
    ACTIVE_FRIENDS = auto()

    # Miscellaneous client-server API
    PEER_LOGIN = auto()
    PEER_LOGOUT = auto()
    ADD_FRIEND = auto()
    REMOVE_FRIEND = auto()
    ADD_BLACKLIST = auto()
    REMOVE_BLACKLIST = auto()
    PEER_UNAVAILABLE = auto()  # TODO: Remove this
    REPLENISH_ONE_TIME_KEYS_REQ = auto()
    REPLENISH_ONE_TIME_KEYS_RESP = auto()


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
            self.sender: Optional[str] = None
            self.receiver: Optional[str] = None
            self.msg_id: CansMsgId = CansMsgId.USER_MESSAGE


class UserMessage(CansMessage):
    """User message."""

    def __init__(self, receiver: str, payload: str) -> None:
        """Create a CANS user message to a peer."""
        super().__init__()
        self.header.msg_id = CansMsgId.USER_MESSAGE
        self.header.receiver = receiver
        self.payload = payload


class PeerHello(CansMessage):
    """Peer handshake."""

    def __init__(self, receiver: str) -> None:
        """Create a peer handshake message."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_HELLO
        self.header.receiver = receiver
        self.payload = CANS_PEER_HANDSHAKE_MAGIC


class SessionEstablished(CansMessage):
    """Session established acknowledgement."""

    def __init__(self, receiver: str) -> None:
        """Create a session established ack message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SESSION_ESTABLISHED
        self.header.receiver = receiver
        self.payload = CANS_PEER_HANDSHAKE_MAGIC


class PeerUnavailable(CansMessage):
    """Peer unavailable notification."""

    def __init__(self, receiver: str, peer: str) -> None:
        """Create a peer unavailable notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_UNAVAILABLE
        self.header.receiver = receiver
        self.header.sender = None
        self.payload = {"peer": peer}


class SchnorrCommit(CansMessage):
    """Commitment of the Schnorr identification scheme."""

    def __init__(self, public_key: str, commitment: str) -> None:
        """Create a Schnorr commitment message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SCHNORR_COMMIT
        self.header.receiver = ""
        self.payload = {
            "public_key": public_key,
            "commitment": commitment,
        }


class SchnorrChallenge(CansMessage):
    """Challenge of the Schnorr identification scheme."""

    def __init__(self, challenge: int) -> None:
        """Create a Schnorr challenge message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SCHNORR_CHALLENGE
        self.header.receiver = ""  # No receiver set during the authentication
        self.payload = {
            "challenge": challenge,
        }


class SchnorrResponse(CansMessage):
    """Response of the Schnorr identification scheme."""

    def __init__(
        self,
        response: int,
        subscriptions: List[str],
        identity_key: str,
        one_time_keys: Dict[str, str],
    ) -> None:
        """Create a Schnorr response message."""
        super().__init__()
        self.header.msg_id = CansMsgId.SCHNORR_RESPONSE
        self.header.receiver = ""
        self.payload = {
            "response": response,
            "subscriptions": subscriptions,
            "identity_key": identity_key,
            "one_time_keys": one_time_keys,
        }


class PeerLogin(CansMessage):
    """Peer login notification."""

    def __init__(
        self,
        receiver: str,
        peer: str,
        public_keys_bundle: PublicKeysBundle,
    ) -> None:
        """Create a peer login notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_LOGIN
        self.header.receiver = receiver
        self.payload = {"peer": peer, "public_keys_bundle": public_keys_bundle}


class PeerLogout(CansMessage):
    """Peer logout notification."""

    def __init__(self, receiver: str, peer: str) -> None:
        """Create a peer logout notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.PEER_LOGOUT
        self.header.receiver = receiver
        self.payload = {"peer": peer}


class AddFriend(CansMessage):
    """Add friend request."""

    def __init__(self, friend: str) -> None:
        """Create an add friend request."""
        super().__init__()
        self.header.msg_id = CansMsgId.ADD_FRIEND
        self.header.receiver = None
        self.payload = {"friend": friend}


class RemoveFriend(CansMessage):
    """Remove friend request."""

    def __init__(self, friend: str) -> None:
        """Create a remove friend request."""
        super().__init__()
        self.header.msg_id = CansMsgId.REMOVE_FRIEND
        self.header.receiver = None
        self.payload = {"friend": friend}


class AddBlacklist(CansMessage):
    """Blacklist users request."""

    def __init__(self, blacklist: List[str]) -> None:
        """Create a blacklist request."""
        super().__init__()
        self.header.msg_id = CansMsgId.ADD_BLACKLIST
        self.header.receiver = None
        self.payload = {"users": blacklist}


class RemoveBlacklist(CansMessage):
    """Whitelist users request."""

    def __init__(self, whitelist: List[str]) -> None:
        """Create a whitelist request."""
        super().__init__()
        self.header.msg_id = CansMsgId.REMOVE_BLACKLIST
        self.header.receiver = None
        self.payload = {"users": whitelist}


class ActiveFriends(CansMessage):
    """Notify the client during handshake who's online."""

    def __init__(
        self,
        receiver: str,
        active_friends: Dict[str, PublicKeysBundle],
    ) -> None:
        """Create an active friends notification."""
        super().__init__()
        self.header.msg_id = CansMsgId.ACTIVE_FRIENDS
        self.header.receiver = receiver
        self.payload = {"friends": active_friends}


class ReplenishOneTimeKeysReq(CansMessage):
    """Send replenish one time keys request to the client."""

    def __init__(self, receiver: str, one_time_keys_num: int) -> None:
        """Create a replenish request."""
        super().__init__()
        self.header.msg_id = CansMsgId.REPLENISH_ONE_TIME_KEYS_REQ
        self.header.sender = None
        self.header.receiver = receiver
        self.payload = {
            "count": one_time_keys_num,
        }


class ReplenishOneTimeKeysResp(CansMessage):
    """Send replenish one time keys response to the server."""

    def __init__(self, one_time_keys: Dict[str, str]) -> None:
        """Create replenish response."""
        super().__init__()
        self.header.msg_id = CansMsgId.REPLENISH_ONE_TIME_KEYS_RESP
        self.header.receiver = None
        self.payload = {
            "keys": one_time_keys,
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
