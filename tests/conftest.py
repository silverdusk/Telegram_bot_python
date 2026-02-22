"""Shared pytest fixtures for app tests."""
import pytest
from unittest.mock import MagicMock

try:
    from cryptography.fernet import Fernet
    _TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()
except Exception:
    # Fallback if cryptography not available (e.g. minimal env)
    _TEST_ENCRYPTION_KEY = "dGVzdF9rZXlfMTIzNDU2Nzg5MGFiY2RlZjAxMjM0NTY3ODkwYWJjZGU="


@pytest.fixture
def mock_settings():
    """Minimal settings object for testing (no real env/file)."""
    s = MagicMock()
    s.min_len_str = 1
    s.max_len_str = 255
    s.max_item_amount = 1_000_000
    s.max_item_price = 999_999.99
    s.allowed_types = ["spare part", "miscellaneous"]
    s.skip_working_hours = True
    s.authorized_ids = []
    s.effective_fallback_admin_ids = []
    s.encryption_key = _TEST_ENCRYPTION_KEY
    return s


@pytest.fixture
def mock_bot():
    """Mock telegram.Bot for BotService tests."""
    return MagicMock()


@pytest.fixture
def mock_context():
    """Mock context with user_data for flow state tests."""
    ctx = MagicMock()
    ctx.user_data = {}
    return ctx
