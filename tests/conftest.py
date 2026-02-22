"""Shared pytest fixtures for app tests."""
import pytest
from unittest.mock import MagicMock


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
