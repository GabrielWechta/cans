"""Abstract away underlying types of keys and their digests."""

from typing import ByteString, Tuple

PubKey = ByteString
PubKeyDigest = ByteString
PublicKeysBundle = Tuple[str, str]
KeyPair = Tuple[str, str]


def digest_key(key: PubKey) -> PubKeyDigest:
    """Digest a key."""
    return key  # TODO: Implement me!
