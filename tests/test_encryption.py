"""Tests for app.core.encryption. Skip entire module if cryptography is not installed."""
import pytest

pytest.importorskip("cryptography")

from app.core.encryption import encrypt_value, decrypt_value


def test_encrypt_decrypt_round_trip():
    """Encrypt then decrypt returns original plaintext."""
    from cryptography.fernet import Fernet
    key_b64 = Fernet.generate_key().decode()
    plain = "secret data"
    cipher = encrypt_value(plain, key_b64)
    assert cipher is not None
    assert cipher != plain
    decrypted = decrypt_value(cipher, key_b64)
    assert decrypted == plain


def test_encrypt_value_raises_when_key_empty():
    """Empty or whitespace key raises ValueError."""
    with pytest.raises(ValueError, match="Encryption key is required"):
        encrypt_value("data", "")
    with pytest.raises(ValueError, match="Encryption key is required"):
        encrypt_value("data", "   ")


def test_decrypt_value_raises_when_key_empty():
    """Empty or whitespace key raises ValueError."""
    with pytest.raises(ValueError, match="Encryption key is required"):
        decrypt_value("cipher", "")
    with pytest.raises(ValueError, match="Encryption key is required"):
        decrypt_value("cipher", "   ")


def test_encrypt_value_returns_none_when_plain_empty():
    """Empty plain returns None (no cipher produced)."""
    from cryptography.fernet import Fernet
    key_b64 = Fernet.generate_key().decode()
    assert encrypt_value("", key_b64) is None


def test_decrypt_value_returns_none_when_cipher_empty():
    """Empty or None cipher returns None."""
    from cryptography.fernet import Fernet
    key_b64 = Fernet.generate_key().decode()
    assert decrypt_value(None, key_b64) is None
    assert decrypt_value("", key_b64) is None


def test_decrypt_value_returns_none_for_invalid_cipher():
    """Invalid or tampered cipher returns None (decryption fails)."""
    from cryptography.fernet import Fernet
    key_b64 = Fernet.generate_key().decode()
    result = decrypt_value("not-valid-fernet-cipher", key_b64)
    assert result is None


def test_encrypt_value_returns_none_for_invalid_key():
    """Invalid base64 or non-Fernet key returns None."""
    result = encrypt_value("data", "not-valid-base64!!!")
    assert result is None
