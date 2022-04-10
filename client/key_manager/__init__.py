"""Client keys manager."""

import sys  # TODO: Remove after PoC

from common.keys import PubKey, PubKeyDigest


class KeyManager:
    """Keeper of the keys."""

    def __init__(self) -> None:
        """Construct a key manager instance."""
        # TODO: Try loading keys from the filesystem
        #       and decrypting the private key.
        #       On failure prompt the user for password

        # TODO: Add dependency to OSAL

        self.public_key_digest = sys.argv[1]  # TODO: Read key from fs
        self.public_key = sys.argv[1]

    def get_own_public_key(self) -> PubKey:
        """Get own public key for authentication purposes."""
        return self.public_key

    def get_own_public_key_digest(self) -> PubKeyDigest:
        """Get own public key digest for routing purposes."""
        return self.public_key_digest
