"""Tests for app.core.validators."""
import pytest
from unittest.mock import patch, MagicMock

from app.core.validators import (
    validate_text_input,
    is_int,
    is_float,
    check_working_hours,
)


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.min_len_str = 1
    s.max_len_str = 255
    return s


class TestValidateTextInput:
    """Tests for validate_text_input."""

    @patch("app.core.validators.get_settings")
    def test_accepts_valid_text(self, get_settings, mock_settings):
        get_settings.return_value = mock_settings
        assert validate_text_input("abc") is True
        assert validate_text_input("Item 123") is True
        assert validate_text_input("a") is True
        assert validate_text_input("x" * 255) is True

    @patch("app.core.validators.get_settings")
    def test_rejects_empty(self, get_settings, mock_settings):
        get_settings.return_value = mock_settings
        assert validate_text_input("") is False

    @patch("app.core.validators.get_settings")
    def test_rejects_too_long(self, get_settings, mock_settings):
        get_settings.return_value = mock_settings
        assert validate_text_input("x" * 256) is False

    @patch("app.core.validators.get_settings")
    def test_respects_custom_length_bounds(self, get_settings, mock_settings):
        get_settings.return_value = mock_settings
        assert validate_text_input("ab", min_len=2, max_len=5) is True
        assert validate_text_input("a", min_len=2, max_len=5) is False
        assert validate_text_input("abcdef", min_len=2, max_len=5) is False

    @patch("app.core.validators.get_settings")
    def test_rejects_invalid_characters(self, get_settings, mock_settings):
        get_settings.return_value = mock_settings
        # Control char / unicode not in allowed set
        assert validate_text_input("bad\x00null") is False
        assert validate_text_input("emoji \U0001f600") is False


class TestIsInt:
    """Tests for is_int."""

    def test_accepts_integers(self):
        assert is_int("0") is True
        assert is_int("1") is True
        assert is_int("-5") is True
        assert is_int("999") is True

    def test_rejects_non_integers(self):
        assert is_int("") is False
        assert is_int("1.5") is False
        assert is_int("abc") is False
        assert is_int("12.0") is False


class TestIsFloat:
    """Tests for is_float."""

    def test_accepts_floats(self):
        assert is_float("0") is True
        assert is_float("1.5") is True
        assert is_float("-3.14") is True
        assert is_float("0.01") is True

    def test_rejects_non_floats(self):
        assert is_float("") is False
        assert is_float("abc") is False
        assert is_float("1.2.3") is False


class TestCheckWorkingHours:
    """Tests for check_working_hours."""

    @patch("app.core.validators.get_settings")
    def test_returns_true_when_skip_working_hours_enabled(self, get_settings, mock_settings):
        mock_settings.skip_working_hours = True
        get_settings.return_value = mock_settings
        assert check_working_hours() is True

    @patch("app.core.validators.get_settings")
    def test_checks_time_when_skip_disabled(self, get_settings, mock_settings):
        mock_settings.skip_working_hours = False
        get_settings.return_value = mock_settings
        # Result depends on current time; we just ensure it returns a bool
        result = check_working_hours()
        assert isinstance(result, bool)
