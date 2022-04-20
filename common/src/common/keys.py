"""Abstract away underlying types of keys and their digests."""

from typing import ByteString, Tuple

PubKey = ByteString
PubKeyDigest = ByteString
PublicKeysBundle = Tuple[str, str]