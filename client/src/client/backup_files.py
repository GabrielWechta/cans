"""CANS application backup files module."""
import glob
import hashlib
import logging
import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple


def gen_save_priv_key_backup_files(
    priv_key: str,
    mnemonics: List[str],
    backups_dir_path: Path,
    enc_save_func: Callable,
) -> None:
    """
    Save Enc(mnemonic, priv_key) do specified directory.

    This is form of keeping save backups for User's priv_key.

    Parameters
    ----------
    priv_key
        Private key to be encrypted.
    mnemonics
        Arbitrary length list of mnemonics. User should have seen those during
        initial setup of the application.
    backups_dir_path
        Path to the backups' directory.
    enc_save_func
        Function used for encrypting and saving encryption
        results to the files.
    """
    for i, mnemonic in enumerate(mnemonics):
        priv_key_backup_path = backups_dir_path / f"priv_key_backup_{i}"
        hashed_mnemonic = hashlib.sha256(mnemonic.encode()).hexdigest()
        enc_save_func(
            plaintext=priv_key,
            path=str(priv_key_backup_path),
            key=hashed_mnemonic,
        )


def attempt_decrypting_priv_key_backup_files(
    alleged_mnemonic: str, backups_dir_path: Path, load_dec_func: Callable
) -> Tuple[bool, Optional[str]]:
    """
    Try to decrypt backup files, using provided mnemonic.

    If decryption was successful, corresponding backup file will be removed
    and function returns True. Otherwise, if decryption failed for all files
     in given directory function returns False.

    Parameters
    ----------
    alleged_mnemonic
        Mnemonic provided by the User.
    backups_dir_path
            Path to the backups' directory.
    load_dec_func
        Function used for loading ciphertext from file and decrypting them.
        This function should be build upon authenticated encryption that raises
        ValueError in the case of failed decryption.

    Returns
    -------
    This function returns
    - True in the case of successful encryption,
    - False if decryption of all backup files in given directory failed.

    """
    key_for_decryption = hashlib.sha256(alleged_mnemonic.encode()).hexdigest()
    log = logging.getLogger("cans-logger")

    for backup_file_path in glob.glob(
        str(backups_dir_path / "priv_key_backup_*")
    ):
        try:
            priv_key = load_dec_func(
                path=backup_file_path, key=key_for_decryption
            )
            log.info(
                f"Successfully decrypted {backup_file_path}. "
                f"Removing that file..."
            )

            os.remove(path=backup_file_path)

            return True, priv_key

        except ValueError:
            log.info(f"Unsuccessful attempt to decrypt {backup_file_path}.")

    return False, None
