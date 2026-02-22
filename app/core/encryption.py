"""Encrypt/decrypt sensitive user data (e.g. credentials) at rest."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def encrypt_value(plain: str, key_b64: str) -> Optional[str]:
    """
    Encrypt string with Fernet (key from config, base64). Key is required (encryption is mandatory).
    Returns None only if plain is empty or on error.
    """
    if not key_b64 or not key_b64.strip():
        raise ValueError("Encryption key is required")
    if not plain:
        return None
    try:
        from cryptography.fernet import Fernet
        # Fernet expects the key as URL-safe base64-encoded bytes (not decoded raw bytes)
        f = Fernet(key_b64.encode())
        return f.encrypt(plain.encode()).decode()
    except Exception as e:
        logger.warning("Encryption failed: %s", e)
        return None


def decrypt_value(cipher: Optional[str], key_b64: str) -> Optional[str]:
    """
    Decrypt Fernet-encrypted string. Key is required (encryption is mandatory).
    Returns None if cipher is empty or on error.
    """
    if not key_b64 or not key_b64.strip():
        raise ValueError("Encryption key is required")
    if not cipher:
        return None
    try:
        from cryptography.fernet import Fernet
        # Fernet expects the key as URL-safe base64-encoded bytes (not decoded raw bytes)
        f = Fernet(key_b64.encode())
        return f.decrypt(cipher.encode()).decode()
    except Exception as e:
        logger.warning("Decryption failed: %s", e)
        return None
