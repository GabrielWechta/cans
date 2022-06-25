"""Test client behaviour when a malformed message is received."""


import asyncio

from cans_client.session_manager_client import SessionManager
from cans_common.keys import digest_key, generate_keys
from cans_common.messages import CansMessage, CansMsgId
from olm import Account


def test_malformed_payload():
    """Test handling incoming message with malformed payload."""
    # Instantiate the session manager
    sm = SessionManager(generate_keys(), Account())

    # Create a malformed message
    message = CansMessage()
    message.header.sender = digest_key(generate_keys()[1])
    message.header.receiver = sm.identity
    message.header.msg_id = CansMsgId.PEER_LOGIN
    message.payload = {
        "unexpected": "For nothing can seem foul to those that win"
    }

    asyncio.get_event_loop().run_until_complete(
        sm._handle_incoming_message(message)
    )
