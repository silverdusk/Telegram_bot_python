"""Tests for app.database.repository (UserRepository)."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.database.repository import UserRepository


class TestUserRepositoryGetByTelegramId:
    """Tests for get_by_telegram_id."""

    def test_returns_user_when_found(self):
        session = MagicMock()
        mock_user = MagicMock()
        mock_user.telegram_user_id = 123
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(session)
        result = asyncio.run(repo.get_by_telegram_id(123))

        assert result is mock_user
        session.execute.assert_called_once()

    def test_returns_none_when_not_found(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(session)
        result = asyncio.run(repo.get_by_telegram_id(999))

        assert result is None

    def test_raises_on_exception(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))

        repo = UserRepository(session)
        with pytest.raises(Exception, match="DB error"):
            asyncio.run(repo.get_by_telegram_id(1))


class TestUserRepositoryListUsers:
    """Tests for list_users."""

    def test_returns_list_when_users_found(self):
        session = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [mock_user]
        session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(session)
        result = asyncio.run(repo.list_users(limit=10))

        assert result == [mock_user]
        session.execute.assert_called_once()

    def test_returns_empty_list_when_no_users(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(session)
        result = asyncio.run(repo.list_users())

        assert result == []


class TestUserRepositoryCreateUser:
    """Tests for create_user."""

    def test_creates_user_when_role_exists(self):
        session = MagicMock()
        mock_role = MagicMock()
        mock_role.id = 1
        mock_role.name = "user"
        role_result = MagicMock()
        role_result.scalar_one_or_none = MagicMock(return_value=mock_role)
        session.execute = AsyncMock(side_effect=[role_result])  # first call: select Role
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = UserRepository(session)
        result = asyncio.run(repo.create_user(telegram_user_id=456, role_name="user"))

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.telegram_user_id == 456
        assert added.role_id == 1
        session.flush.assert_called_once()
        session.refresh.assert_called_once_with(added)
        assert result is added

    def test_raises_when_role_not_found(self):
        session = MagicMock()
        role_result = MagicMock()
        role_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=role_result)
        session.rollback = AsyncMock()

        repo = UserRepository(session)
        with pytest.raises(ValueError, match="Role admin not found"):
            asyncio.run(repo.create_user(telegram_user_id=1, role_name="admin"))

    def test_rollback_on_exception(self):
        session = MagicMock()
        mock_role = MagicMock()
        mock_role.id = 1
        role_result = MagicMock()
        role_result.scalar_one_or_none = MagicMock(return_value=mock_role)
        session.execute = AsyncMock(return_value=role_result)
        session.add = MagicMock()
        session.flush = AsyncMock(side_effect=Exception("flush failed"))
        session.rollback = AsyncMock()

        repo = UserRepository(session)
        with pytest.raises(Exception, match="flush failed"):
            asyncio.run(repo.create_user(telegram_user_id=1, role_name="user"))
        session.rollback.assert_called_once()


class TestUserRepositorySetRole:
    """Tests for set_role."""

    def test_updates_role_when_user_found(self):
        session = MagicMock()
        mock_user = MagicMock()
        mock_user.role_id = 1
        mock_role = MagicMock()
        mock_role.id = 2
        mock_role.name = "admin"
        user_result = MagicMock()
        user_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        role_result = MagicMock()
        role_result.scalar_one_or_none = MagicMock(return_value=mock_role)
        session.execute = AsyncMock(side_effect=[user_result, role_result])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = UserRepository(session)
        result = asyncio.run(repo.set_role(telegram_user_id=111, role_name="admin"))

        assert result is mock_user
        assert mock_user.role_id == 2
        session.flush.assert_called_once()
        session.refresh.assert_called_once_with(mock_user)

    def test_returns_none_when_user_not_found(self):
        session = MagicMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=user_result)

        repo = UserRepository(session)
        result = asyncio.run(repo.set_role(telegram_user_id=999, role_name="admin"))

        assert result is None

    def test_raises_when_role_not_found(self):
        session = MagicMock()
        mock_user = MagicMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        role_result = MagicMock()
        role_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(side_effect=[user_result, role_result])
        session.rollback = AsyncMock()

        repo = UserRepository(session)
        with pytest.raises(ValueError, match="Role invalid not found"):
            asyncio.run(repo.set_role(telegram_user_id=1, role_name="invalid"))


class TestUserRepositoryDeleteUser:
    """Tests for delete_user."""

    def test_returns_true_when_row_deleted(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        repo = UserRepository(session)
        result = asyncio.run(repo.delete_user(telegram_user_id=123))

        assert result is True
        session.execute.assert_called_once()
        session.flush.assert_called_once()

    def test_returns_false_when_no_row_deleted(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        repo = UserRepository(session)
        result = asyncio.run(repo.delete_user(telegram_user_id=999))

        assert result is False

    def test_rollback_on_exception(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        session.rollback = AsyncMock()

        repo = UserRepository(session)
        with pytest.raises(Exception, match="DB error"):
            asyncio.run(repo.delete_user(telegram_user_id=1))
        session.rollback.assert_called_once()
