"""Encryption utility."""

from olm import Account


class EncryptionUtility:
    def __init__(self) -> None:
        self.account = Account()
        print(self.account.identity_keys)
        # pass
