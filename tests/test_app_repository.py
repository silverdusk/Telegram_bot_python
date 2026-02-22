"""Tests for app.database.repository (ItemRepository)."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.database.repository import ItemRepository
from app.schemas.item import ItemUpdate


class TestItemRepositoryGetItemById:
    """Tests for get_item_by_id."""

    def test_returns_item_when_found(self):
        session = MagicMock()
        mock_item = MagicMock()
        mock_item.id = 42
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_item)
        session.execute = AsyncMock(return_value=mock_result)

        repo = ItemRepository(session)
        result = asyncio.run(repo.get_item_by_id(42))

        assert result is mock_item
        session.execute.assert_called_once()

    def test_returns_none_when_not_found(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=mock_result)

        repo = ItemRepository(session)
        result = asyncio.run(repo.get_item_by_id(999))

        assert result is None

    def test_raises_on_exception(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))

        repo = ItemRepository(session)
        with pytest.raises(Exception, match="DB error"):
            asyncio.run(repo.get_item_by_id(1))


class TestItemRepositoryUpdateItem:
    """Tests for update_item."""

    def test_returns_updated_item_when_found(self):
        session = MagicMock()
        mock_item = MagicMock()
        mock_item.id = 10
        mock_item.item_name = "Old"
        mock_item.item_amount = 1
        repo = ItemRepository(session)
        repo.get_item_by_id = AsyncMock(return_value=mock_item)
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        payload = ItemUpdate(item_name="New", item_amount=5)
        result = asyncio.run(repo.update_item(10, payload))

        assert result is mock_item
        assert mock_item.item_name == "New"
        assert mock_item.item_amount == 5
        session.flush.assert_called_once()
        session.refresh.assert_called_once_with(mock_item)

    def test_returns_none_when_item_not_found(self):
        session = MagicMock()
        repo = ItemRepository(session)
        repo.get_item_by_id = AsyncMock(return_value=None)

        payload = ItemUpdate(item_name="X")
        result = asyncio.run(repo.update_item(999, payload))

        assert result is None
        session.flush.assert_not_called()

    def test_rollback_on_exception(self):
        session = MagicMock()
        session.rollback = AsyncMock()
        mock_item = MagicMock()
        repo = ItemRepository(session)
        repo.get_item_by_id = AsyncMock(return_value=mock_item)
        session.flush = AsyncMock(side_effect=Exception("flush failed"))

        with pytest.raises(Exception, match="flush failed"):
            asyncio.run(repo.update_item(1, ItemUpdate(item_name="X")))

        session.rollback.assert_called_once()


class TestItemRepositoryDeleteByNameAndChat:
    """Tests for delete_by_name_and_chat."""

    def test_returns_rowcount_when_rows_deleted(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 2
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        repo = ItemRepository(session)
        deleted = asyncio.run(repo.delete_by_name_and_chat("Widget", chat_id=123))

        assert deleted == 2
        session.execute.assert_called_once()
        session.flush.assert_called_once()

    def test_returns_zero_when_rowcount_none(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = None
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        repo = ItemRepository(session)
        deleted = asyncio.run(repo.delete_by_name_and_chat("NoMatch", chat_id=456))

        assert deleted == 0

    def test_returns_zero_when_no_rows_deleted(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        repo = ItemRepository(session)
        deleted = asyncio.run(repo.delete_by_name_and_chat("Missing", chat_id=789))

        assert deleted == 0

    def test_rollback_on_exception(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        session.rollback = AsyncMock()

        repo = ItemRepository(session)
        with pytest.raises(Exception, match="DB error"):
            asyncio.run(repo.delete_by_name_and_chat("X", chat_id=1))

        session.rollback.assert_called_once()
