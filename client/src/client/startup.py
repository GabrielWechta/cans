"""Startup Component."""

import getpass
import hashlib
import subprocess
from os import mkdir, path
from pathlib import Path
from shutil import rmtree

from Cryptodome.Cipher import AES, _mode_gcm
from Cryptodome.Util.Padding import pad, unpad
from olm import Account

from common.keys import (
    EcPemKeyPair,
    generate_keys,
    get_private_key_from_pem,
    get_public_key_pem,
)


class Startup:
    """Startup Component.

    Create application directory, provide paths to keys and database,
    derive hardware fingerprint, generate user's EC keys, generate AES
    key to encrypt/decrypt database plus private key.
    """

    def __init__(self) -> None:
        """Intialize application data paths."""
        self._home_dir = Path.home() / ".cans"
        self._keys_dir = self._home_dir / "keys"
        self.db_path = self._home_dir / "user_data.db"
        self.user_public_key_path = self._keys_dir / "pub.pem"
        self.user_private_key_path = self._keys_dir / "priv.pem"
        self.crypto_account_path = self._home_dir / "crypto_account"

    def cans_setup(self) -> None:
        """Create all necessary directories."""
        rmtree(path=self._home_dir, ignore_errors=True)
        mkdir(self._home_dir, mode=0o700)
        mkdir(self._keys_dir, mode=0o700)

    def is_first_startup(self) -> bool:
        """Check if user's EC EcPemKeyPair exists."""
        pub_key_exists = path.isfile(self.user_public_key_path)
        priv_key_exists = path.isfile(self.user_private_key_path)
        crypto_account_exists = path.isfile(self.crypto_account_path)

        return not (
            pub_key_exists and priv_key_exists and crypto_account_exists
        )

    def create_crypto_account(self, passphrase: str) -> Account:
        """Create a libolm Account() object and store it."""
        account = Account()
        pickled = account.pickle(passphrase)
        with open(self.crypto_account_path, "wb") as fd:
            fd.write(pickled)
        return account

    def load_crypto_account(self, passphrase: str) -> Account:
        """Load an existing libolm Account() object."""
        with open(self.crypto_account_path, "rb") as fd:
            pickled = fd.read()
            account = Account.from_pickle(pickled, passphrase)
            return account

    def _hardware_fingerprint(self) -> str:
        """Derive a fingerprint from system hardware.

        Return sha256 hash of: UUID of a drive + model of CPU +
        username of os user account.
        """
        try:
            drive_UUID = str(
                subprocess.check_output(
                    "/usr/bin/blkid -s UUID -o value | /usr/bin/head -n 1"
                )
            )
            cpu_model = str(
                subprocess.check_output(
                    "/usr/bin/lscpu | /usr/bin/grep 'Model name' "
                    + "| /usr/bin/cut -f 2 -d ':' "
                    + "| /usr/bin/awk '{$1=$1}1'"
                )
            )
            username = getpass.getuser()
        except Exception:
            # If in docker container and no devices present
            # use default placeholder values.
            drive_UUID = "3255683f-53a2-4fdf-91cf-b4c1041e2a62"
            cpu_model = "Intel(R) Core(TM) i7-10870H CPU @ 2.20GHz"
            username = "eve"

        return hashlib.sha256(
            (drive_UUID + cpu_model + username).encode()
        ).hexdigest()

    def get_key(self, passphrase: str = "") -> str:
        """Derive AES key based on argon2 hash of hwf and passphrase."""
        return hashlib.sha256(
            (self._hardware_fingerprint() + passphrase).encode("utf-8")
        ).hexdigest()

    def generate_private_key(self, password: str) -> None:
        """Run Cryptodome to generate EC private key.

        Encrypt and save generated private key to the .cans/keys directory.
        """
        priv_key, _ = generate_keys()

        # Encrypt private key with AES-GCM using password
        with open(self.user_private_key_path, "wb") as private_key_file:
            cipher = AES.new(password.encode("utf-8")[:32], AES.MODE_GCM)
            enc_priv_key = cipher.encrypt(
                pad(priv_key.encode("utf-8"), AES.block_size)
            )
            if isinstance(cipher, _mode_gcm.GcmMode):
                # Save tag at the beginning of the file
                private_key_file.write(cipher.nonce)
            private_key_file.write(enc_priv_key)

    def _decrypt_private_key(self, password: str) -> str:
        """Decrypt the private key."""
        # Read private key from file
        with open(self.user_private_key_path, "rb") as private_key_file:
            iv = private_key_file.read(16)
            enc_priv_key = private_key_file.read()

        cipher = AES.new(password.encode("utf-8")[:32], AES.MODE_GCM, nonce=iv)
        return unpad(cipher.decrypt(enc_priv_key), AES.block_size).decode(
            "utf8"
        )

    def load_key_pair(self, password: str) -> EcPemKeyPair:
        """Decrypt and verify if private key is correct.

        Regenerate keys if private key is corrupted. Return both keys.
        """
        pub_key = ""
        priv_key = ""

        try:
            # Check if padding is correct
            priv_key = self._decrypt_private_key(password)
            # Check it's a valid EC key
            get_private_key_from_pem(priv_key)
        except ValueError:
            # Corrupted key so generate new key pair
            # TODO Figure out if this is correct approach
            self.generate_private_key(password)
            priv_key = self._decrypt_private_key(password)

        pub_key = get_public_key_pem(priv_key)

        return priv_key, pub_key
