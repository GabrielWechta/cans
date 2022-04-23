"""ClientSession tests."""

from server.client_session import ClientSession


def test_dummy():
    """A dummy test."""
    session = ClientSession(
        conn=None,
        public_key_digest=None,
        subscriptions=None,
        identity_key=None,
        one_time_keys={
            "1": "hello",
            "2": "darkness",
            "3": "my",
            "4": "old",
            "5": "friend",
        },
    )

    session.pop_one_time_key()
    assert len(session.one_time_keys) == 4
