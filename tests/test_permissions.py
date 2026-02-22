"""Tests for app.core.permissions. Uses conftest.mock_settings (effective_fallback_admin_ids set per test)."""
import asyncio
from unittest.mock import MagicMock, AsyncMock

from app.core.permissions import get_user_role, is_admin_role, can_manage_item


def test_get_user_role_returns_none_when_user_id_none(mock_settings):
    """user_id None returns None."""
    session = MagicMock()
    result = asyncio.run(get_user_role(None, session, mock_settings))
    assert result is None
    session.execute.assert_not_called()


def test_get_user_role_returns_role_from_db_when_user_found(mock_settings):
    """When session returns a user with role, return that role name."""
    session = MagicMock()
    user = MagicMock()
    user.role = MagicMock()
    user.role.name = "admin"
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result_mock)

    result = asyncio.run(get_user_role(123, session, mock_settings))

    assert result == "admin"


def test_get_user_role_returns_user_role_from_db(mock_settings):
    """When session returns a user with role 'user', return 'user'."""
    session = MagicMock()
    user = MagicMock()
    user.role = MagicMock()
    user.role.name = "user"
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result_mock)

    result = asyncio.run(get_user_role(456, session, mock_settings))

    assert result == "user"


def test_get_user_role_fallback_admin_when_user_not_in_db(mock_settings):
    """When session returns None and user_id is in effective_fallback_admin_ids, return 'admin'."""
    mock_settings.effective_fallback_admin_ids = [111, 222]
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    result = asyncio.run(get_user_role(111, session, mock_settings))

    assert result == "admin"


def test_get_user_role_fallback_user_when_not_in_db_and_not_in_fallback(mock_settings):
    """When session returns None and user_id not in fallback, return 'user'."""
    mock_settings.effective_fallback_admin_ids = [111]
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    result = asyncio.run(get_user_role(999, session, mock_settings))

    assert result == "user"


def test_get_user_role_fallback_admin_when_session_raises(mock_settings):
    """When session.execute raises, use effective_fallback_admin_ids; in list -> 'admin'."""
    mock_settings.effective_fallback_admin_ids = [777]
    session = MagicMock()
    session.execute = AsyncMock(side_effect=Exception("DB error"))

    result = asyncio.run(get_user_role(777, session, mock_settings))

    assert result == "admin"


def test_get_user_role_fallback_user_when_session_raises_and_not_in_fallback(mock_settings):
    """When session.execute raises and user_id not in fallback, return 'user'."""
    mock_settings.effective_fallback_admin_ids = [111]
    session = MagicMock()
    session.execute = AsyncMock(side_effect=Exception("DB error"))

    result = asyncio.run(get_user_role(888, session, mock_settings))

    assert result == "user"


class TestIsAdminRole:
    """Tests for is_admin_role."""

    def test_true_for_admin(self):
        assert is_admin_role("admin") is True

    def test_false_for_user(self):
        assert is_admin_role("user") is False

    def test_false_for_none(self):
        assert is_admin_role(None) is False


class TestCanManageItem:
    """Tests for can_manage_item."""

    def test_admin_can_manage_any(self):
        """Admin can manage any item regardless of created_by_user_id."""
        assert can_manage_item(None, 1, "admin") is True
        assert can_manage_item(2, 1, "admin") is True
        assert can_manage_item(1, 1, "admin") is True

    def test_user_can_manage_only_own_item(self):
        """User can manage only when created_by_user_id == current_user_id."""
        assert can_manage_item(1, 1, "user") is True
        assert can_manage_item(2, 1, "user") is False

    def test_user_cannot_manage_when_creator_none(self):
        """User cannot manage item with no creator (legacy items)."""
        assert can_manage_item(None, 1, "user") is False

    def test_false_when_current_user_id_none(self):
        assert can_manage_item(1, None, "admin") is False
        assert can_manage_item(1, None, "user") is False

    def test_false_when_role_none(self):
        assert can_manage_item(1, 1, None) is False

    def test_false_for_unknown_role(self):
        """Non-admin, non-user role returns False."""
        assert can_manage_item(1, 1, "other") is False
