"""Testing creating and recovering from backup files."""
import glob
from pathlib import Path

import pytest

from client.backup_files import (
    attempt_decrypting_priv_key_backup_files,
    gen_save_priv_key_backup_files,
)
from client.startup import Startup


@pytest.fixture
def gen_mnemonics():
    """Generate mnemonics."""
    startup = Startup()
    mnemonics = startup.generate_mnemonics(count=10, char_length=10)
    return mnemonics


@pytest.fixture(scope="function")
def gen_save_10_priv_key_backup_files(tmp_path, gen_mnemonics):
    """Generate 10 backup files."""
    tmp_dir_path = Path(tmp_path)
    mnemonics = gen_mnemonics
    gen_save_priv_key_backup_files(
        priv_key="Fairisfoulandfoulisfair",
        mnemonics=mnemonics,
        backups_dir_path=tmp_dir_path,
        enc_save_func=Startup().encrypt_on_disk,
    )
    return tmp_dir_path


def test_backup_files_creation(gen_save_10_priv_key_backup_files):
    """Test if all 10 backup files are where they should be."""
    tmp_dir_path = gen_save_10_priv_key_backup_files
    backup_files_num = len(glob.glob(str(tmp_dir_path / "*")))
    assert backup_files_num == 10, (
        f"There are {backup_files_num} in {tmp_dir_path},"
        f" but there should be 10."
    )


def test_bad_attempt_decrypting_priv_key_backup_files(
    gen_save_10_priv_key_backup_files,
):
    """Test if decryption fails for nonsense mnemonic."""
    tmp_dir_path = gen_save_10_priv_key_backup_files
    nonsense_mnemonic = "DoubledoubletoilandtroubleFireburnandcauldronbubble"
    success, _ = attempt_decrypting_priv_key_backup_files(
        alleged_mnemonic=nonsense_mnemonic,
        backups_dir_path=tmp_dir_path,
        load_dec_func=Startup().decrypt_from_disk,
    )

    assert success is False, (
        f"Mnemonic {nonsense_mnemonic} decrypted one of backup files, "
        f"although it should not."
    )


def test_good_attempt_decrypting_priv_key_backup_files(
    gen_save_10_priv_key_backup_files, gen_mnemonics
):
    """Test if all backup files decrypt correctly."""
    tmp_dir_path = gen_save_10_priv_key_backup_files
    mnemonics = gen_mnemonics
    for mnemonic in mnemonics:
        success, _ = attempt_decrypting_priv_key_backup_files(
            alleged_mnemonic=mnemonic,
            backups_dir_path=tmp_dir_path,
            load_dec_func=Startup().decrypt_from_disk,
        )

        assert success is True, f"Mnemonic {mnemonic} did not decode any file."
