"""Startup Component."""

import getpass
import hashlib
import logging
import os
import secrets
import subprocess
from pathlib import Path
from shutil import rmtree
from typing import List

from Cryptodome.Cipher import AES, _mode_gcm
from olm import Account

from common.keys import (
    EcPemKeyPair,
    generate_keys,
    get_private_key_from_pem,
    get_public_key_pem,
)

from .backup_files import gen_save_priv_key_backup_files


class Startup:
    """Startup Component.

    Create application directory, provide paths to keys and database,
    derive hardware fingerprint, generate user's EC keys, generate AES
    key to encrypt/decrypt database plus private key.
    """

    def __init__(self) -> None:
        """Initialize application data paths."""
        self._home_dir = Path.home() / ".cans"
        self._keys_dir = self._home_dir / "keys"
        self.backups_dir = self._home_dir / "backups"
        self.db_path = self._home_dir / "user_data.db"
        self.user_private_key_path = self._keys_dir / "priv.pem"
        self.crypto_account_path = self._home_dir / "crypto_account"

        self.log = logging.getLogger("cans-logger")

    def cans_setup(self) -> None:
        """Create all necessary directories."""
        rmtree(path=self._home_dir, ignore_errors=True)
        os.mkdir(self._home_dir, mode=0o700)
        os.mkdir(self._keys_dir, mode=0o700)
        os.mkdir(self.backups_dir, mode=0o700)

    def is_first_startup(self) -> bool:
        """Check if user's EC EcPemKeyPair exists."""
        priv_key_exists = os.path.isfile(self.user_private_key_path)
        crypto_account_exists = os.path.isfile(self.crypto_account_path)

        return not (priv_key_exists and crypto_account_exists)

    def create_crypto_account(self, passphrase: str) -> Account:
        """Create a libolm Account() object and store it."""
        account = Account()
        pickled = account.pickle(passphrase)
        fd = os.open(
            path=self.crypto_account_path,
            flags=os.O_CREAT | os.O_WRONLY,
            mode=0o700,
        )
        os.write(fd, pickled)
        return account

    def load_crypto_account(self, passphrase: str) -> Account:
        """Load an existing libolm Account() object."""
        fd = os.open(path=self.crypto_account_path, flags=os.O_RDONLY)
        pickled = os.read(fd, os.path.getsize(self.crypto_account_path))
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
                    "/usr/bin/blkid -s UUID -o value | /usr/bin/head -n 1",
                    shell=True,
                )
            )  # fbd47eaa
            cpu_model = str(
                subprocess.check_output(
                    "/usr/bin/lscpu | /usr/bin/grep 'Model name' "
                    + "| /usr/bin/cut -f 2 -d ':' "
                    + "| /usr/bin/awk '{$1=$1}1'",
                    shell=True,
                )
            )
            username = getpass.getuser()
        except Exception as e:
            # If in docker container and no devices present
            # use default placeholder values.
            self.log.error(f"HWF derivation error: {str(e)}")
            drive_UUID = "3255683f-53a2-4fdf-91cf-b4c1041e2a62"
            cpu_model = "Intel(R) Core(TM) i7-10870H CPU @ 2.20GHz"
            username = "eve"

        return hashlib.sha256(
            (drive_UUID + cpu_model + username).encode()
        ).hexdigest()

    def get_key(self, passphrase: str = "") -> str:
        """Derive AES key based on hash of hwf and passphrase."""
        return hashlib.sha256(
            (self._hardware_fingerprint() + passphrase).encode("utf-8")
        ).hexdigest()

    def get_app_password(self, priv_key: str) -> str:
        """Get a password used to encrypt database and Olm account."""
        return hashlib.sha256(priv_key.encode()).hexdigest()

    def _encrypt(self, key: str, plaintext: str) -> bytes:
        """Use AES-GCM to encrypt a given plaintext."""
        key_bytes = bytes.fromhex(key)
        data = plaintext.encode()

        cipher = AES.new(key_bytes, AES.MODE_GCM)
        assert isinstance(cipher, _mode_gcm.GcmMode)

        ciphertext, tag = cipher.encrypt_and_digest(data)

        return cipher.nonce + tag + ciphertext

    def _decrypt(self, key: str, ciphertext: bytes) -> str:
        """Use AES-GCM to decrypt a given ciphertext.

        This function raises ValueError if the MAC tag is not valid,
        that is, if the entire message should not be trusted.
        """
        key_bytes = bytes.fromhex(key)

        cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=ciphertext[:16])
        assert isinstance(cipher, _mode_gcm.GcmMode)

        plaintext = cipher.decrypt_and_verify(
            ciphertext=ciphertext[32:], received_mac_tag=ciphertext[16:32]
        )

        return plaintext.decode()

    def encrypt_on_disk(self, plaintext: str, path: str, key: str) -> None:
        """Encrypt given plaintext and store it in a file."""
        fd = os.open(path=path, flags=os.O_CREAT | os.O_WRONLY, mode=0o700)
        ciphertext = self._encrypt(key=key, plaintext=plaintext)
        os.write(fd, ciphertext)

    def decrypt_from_disk(self, path: str, key: str) -> str:
        """Decrypt data from a given file and return it."""
        fd = os.open(path=path, flags=os.O_RDONLY)
        ciphertext = os.read(fd, os.path.getsize(path))
        return self._decrypt(key=key, ciphertext=ciphertext)

    def generate_private_key(self, password: str) -> None:
        """Run Cryptodome to generate EC private key.

        Encrypt and save generated private key to the .cans/keys directory.
        """
        priv_key, _ = generate_keys()

        # Encrypt private key with AES-GCM using password
        self.encrypt_on_disk(
            plaintext=priv_key,
            path=str(self.user_private_key_path),
            key=password,
        )

    def load_key_pair(self, password: str) -> EcPemKeyPair:
        """Decrypt and verify if private key is correct.

        Return private and public key.
        """
        priv_key = self.decrypt_from_disk(
            path=str(self.user_private_key_path), key=password
        )
        # Check it's a valid EC key
        get_private_key_from_pem(priv_key)
        pub_key = get_public_key_pem(priv_key)

        return priv_key, pub_key

    @staticmethod
    def generate_mnemonics(count: int, char_length: int) -> List[str]:
        """Generate mnemonics values with given parameters."""
        mnemonics = [secrets.token_hex(char_length // 2) for _ in range(count)]
        return mnemonics

    def produce_priv_key_backup_files(
        self, priv_key: str, mnemonics: List[str]
    ) -> None:
        """Produce priv_key backup files using mnemonics."""
        gen_save_priv_key_backup_files(
            priv_key=priv_key,
            mnemonics=mnemonics,
            backups_dir_path=self.backups_dir,
            enc_save_func=self.encrypt_on_disk,
        )
