"""Startup Component."""

import getpass
import hashlib
import subprocess
from os import mkdir, path
from pathlib import Path
from shutil import rmtree

import argon2
from olm import Account

from common.keys import KeyPair


class Startup:
    """Startup Component.

    Create application directory, provide paths to keys and database,
    derive hardware fingerprint, generate user's RSA keys, generate AES
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
        """Check if user's RSA KeyPair exists."""
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
                subprocess.check_output("blkid -s UUID -o value | head -n 1")
            )
            cpu_model = str(
                subprocess.check_output(
                    "lscpu | grep 'Model name' | cut -f 2 -d \":\" "
                    + "| awk '{$1=$1}1'"
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

    def get_key(self, passphrase: str = "") -> bytes:
        """Derive AES key based on argon2 hash of hwf and passphrase."""
        hwf = self._hardware_fingerprint()
        return argon2.low_level.hash_secret_raw(
            secret=(hwf + passphrase).encode("utf-8"),
            salt=hwf.encode("utf-8"),
            type=argon2.low_level.Type(2),
            time_cost=argon2.DEFAULT_TIME_COST,
            memory_cost=argon2.DEFAULT_MEMORY_COST,
            parallelism=argon2.DEFAULT_PARALLELISM,
            hash_len=32,
        )

    def generate_key_pair(self, password: str) -> KeyPair:
        """Run OpenSSL to generate a pair of RSA keys.

        Save generated values to the .cans/keys directory.
        """
        priv_key = str(
            subprocess.run(
                "openssl genrsa 4096",
                capture_output=True,
                text=True,
                shell=True,
            ).stdout
        )

        with open(self.user_private_key_path, "w") as private_key_file:
            private_key_file.write(priv_key)

        pub_key = str(
            subprocess.run(
                "openssl rsa -in "
                + self.user_private_key_path.as_posix()
                + " -pubout",
                capture_output=True,
                text=True,
                shell=True,
            ).stdout
        )

        with open(self.user_public_key_path, "w") as public_key_file:
            public_key_file.write(pub_key)

        # TODO: Encrypt private key
        password = password

        # TODO: Clean up keys before returning them
        return pub_key, priv_key

    def decrypt_key_pair(self, password: str) -> KeyPair:
        """Decrypt key files and return them."""
        pub_key = ""
        priv_key = ""
        # Read public key from file
        with open(self.user_public_key_path, "r") as public_key_file:
            pub_key = public_key_file.read()

        # Read private key from file
        with open(self.user_private_key_path, "r") as private_key_file:
            priv_key = private_key_file.read()

        # TODO: Decrypt keys
        password = password

        # TODO: Clean up keys before returning them
        return pub_key, priv_key
