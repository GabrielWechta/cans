"""Operating System Abstraction Layer."""

import getpass
import hashlib
import subprocess
from os import mkdir, path
from pathlib import Path


class OSAL:
    """Operating System Abstraction Layer.

    Create application directory, provide access to specific paths
    and derive hardware fingerprint.
    """

    def __init__(self) -> None:
        """Intialize application data paths."""
        self._home_dir = Path.home() / ".cans"
        self._db_path = self._home_dir / "user_data.db"
        self._keys_dir = self._home_dir / "keys"
        self.__cans_setup()

    def __cans_setup(self) -> None:
        """Create .cans folder if it doesn't exist."""
        if not path.isdir(self._home_dir):
            mkdir(self._home_dir, mode=0o700)
            mkdir(self._keys_dir, mode=0o700)
        if not path.isdir(self._keys_dir):
            mkdir(self._keys_dir, mode=0o700)

    def database_path(self) -> Path:
        """Return path to database file."""
        return self._db_path

    def keys_directory(self) -> Path:
        """Return path to keys directory."""
        return self._keys_dir

    def hardware_fingerprint(self) -> str:
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
