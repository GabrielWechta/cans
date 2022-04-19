"""Encryption utility."""

from olm import Account, InboundSession, OutboundSession

from resources.olm.python.olm import OlmPreKeyMessage


class TripleDiffieHellmanInterface:
    """Class for managing Triple Diffie Hellman protocol."""

    def __int__(self, account: Account) -> None:
        """Initialize interface for Triple Diffie Hellman."""
        self.account = account

    def get_one_time_keys(self, number_of_keys: int) -> dict:
        """Get public one time keys."""
        self.account.generate_one_time_keys(number_of_keys)
        one_time_keys = self.account.one_time_keys
        self.account.mark_keys_as_published()
        return one_time_keys

    def get_identity_key(self) -> str:
        """Get public identity key."""
        return self.account.identity_keys["curve25519"]


class DoubleRatchetSession:
    """Class for managing Double Ratchet single session."""

    def __init__(self, account: Account) -> None:
        """Initialize basic configuration for Double Ratchet Session."""
        self.account = account
        self.session = None

    def start_outbound_session(
        self, peer_id_key: str, peer_one_time_key: str
    ) -> None:
        """Start outbound (this account is an initiator) session."""
        self.session = OutboundSession(
            account=self.account,
            identity_key=peer_id_key,
            one_time_key=peer_one_time_key,
        )

    def start_inbound_session(self, pre_key_message: OlmPreKeyMessage) -> None:
        """Start inbound (this account is a receiver) session."""
        self.session = InboundSession(
            account=self.account, message=pre_key_message
        )

    def encrypt(self, plaintext: str) -> str:
        """Interface for encrypting plaintext for both types of sessions."""
        assert self.session is not None, (
            f"Can't encrypt {plaintext}. "
            f"This account does not have initialized DR session."
        )

        ciphertext = self.session.encrypt(plaintext=plaintext)
        return ciphertext

    def decrypt(self, ciphertext: str) -> str:
        """Interface for decrypting ciphertext for both types of sessions."""
        assert self.session is not None, (
            f"Can't decrypt {ciphertext}. "
            f"This account does not have initialized DR session."
        )

        return self.session.decrypt(ciphertext=ciphertext)
