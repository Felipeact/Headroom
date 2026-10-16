"""Plaid access token encryption (AD-038). Nothing outside `bank_sync` encrypts or decrypts."""

from cryptography.fernet import Fernet, MultiFernet

from app.settings import get_settings


def _fernet() -> MultiFernet:
    # The first key encrypts; every key decrypts, so a new key can go first.
    return MultiFernet([Fernet(key) for key in get_settings().token_encryption_keys])


def encrypt_access_token(access_token: str) -> str:
    return _fernet().encrypt(access_token.encode()).decode()


def decrypt_access_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
