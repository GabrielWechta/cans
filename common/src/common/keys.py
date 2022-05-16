"""Abstract away underlying types of keys and their digests."""

import hashlib
from typing import Tuple

from Cryptodome.PublicKey import ECC

PublicKeysBundle = Tuple[str, str]
KeyPair = Tuple[str, str]

PKI_CURVE_NAME = "prime256v1"


def digest_key(key: str) -> str:
    """Digest a key."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_private_key_from_pem(pem: str) -> int:
    """Parse a PEM file and return a private key as an integer."""
    return int(ECC.import_key(encoded=pem, curve_name=PKI_CURVE_NAME).d)


def get_schnorr_commitment() -> Tuple[int, str]:
    """Get Schnorr commitment values."""
    commitment = ECC.generate(curve=PKI_CURVE_NAME)
    secret = int(commitment.d)
    encoded_public = commitment.public_key().export_key(format="PEM")
    return secret, str(encoded_public)


def get_schnorr_challenge() -> int:
    """Choose a random Schnorr challenge."""
    # Generate a valid key pair and return the private component as a challenge
    key = ECC.generate(curve=PKI_CURVE_NAME)
    return int(key.d)


def get_schnorr_response(
    private_key: int, ephemeral: int, challenge: int
) -> int:
    """Compute Schnorr response."""
    return (ephemeral + private_key * challenge) % int(
        ECC._curves[PKI_CURVE_NAME].order
    )


def schnorr_verify(
    public_key: str, commitment: str, challenge: int, response: int
) -> bool:
    """Verify Schnorr protocol."""
    # TODO: Add error handling if point decoding fails

    # Recover EccPoint from PEM-encoded commitment
    commit_point = ECC.import_key(
        encoded=commitment,
        curve_name=PKI_CURVE_NAME,
    ).pointQ

    # Recover EccPoint from PEM-encoded public key
    pubkey_point = ECC.import_key(
        encoded=public_key,
        curve_name=PKI_CURVE_NAME,
    ).pointQ

    # Create a point based on the response (scalar) and group generator (s * G)
    response_point = (
        ECC.construct(curve=PKI_CURVE_NAME, d=response).public_key().pointQ
    )

    return pubkey_point * challenge + commit_point == response_point
