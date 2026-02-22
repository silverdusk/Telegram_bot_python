"""Tests for app.database.repository (ItemRepository)."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.database.repository import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate


@patch("app.core.config.get_settings")
class TestItemRepositoryCreateItem:
    """Tests for create_item."""

    def test_creates_item_and_returns_it(self, get_settings):
        mock_settings = MagicMock()
        mock_settings.allowed_types = ["spare part", "miscellaneous"]
        get_settings.return_value = mock_settings

        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = ItemRepository(session)
        item_data = ItemCreate(
            item_name="Widget",
            item_amount=2,
            item_type="spare part",
            item_price=1.5,
            availability=True,
        )
        result = asyncio.run(repo.create_item(item_data, chat_id=100))

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.item_name == "Widget"
        assert added.item_amount == 2
        assert added.chat_id == 100
        assert added.created_by_user_id is None
        session.flush.assert_called_once()
        session.refresh.assert_called_once_with(added)
        assert result is added

    def test_creates_item_with_created_by_user_id(self, get_settings):
        mock_settings = MagicMock()
        mock_settings.allowed_types = ["spare part", "miscellaneous"]
        get_settings.return_value = mock_settings
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = ItemRepository(session)
        item_data = ItemCreate(
            item_name="Thing",
            item_amount=1,
            item_type="miscellaneous",
            availability=False,
        )
        result = asyncio.run(repo.create_item(item_data, chat_id=200, created_by_user_id=42))

        added = session.add.call_args[0][0]
        assert added.created_by_user_id == 42
        assert result is added

    def test_rollback_on_exception(self, get_settings):
        mock_settings = MagicMock()
        mock_settings.allowed_types = ["spare part"]
        get_settings.return_value = mock_settings
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock(side_effect=Exception("flush failed"))
        session.rollback = AsyncMock()

        repo = ItemRepository(session)
        item_data = ItemCreate(
            item_name="X",
            item_amount=1,
            item_type="spare part",
            availability=False,
        )
        with pytest.raises(Exception, match="flush failed"):
            asyncio.run(repo.create_item(item_data, chat_id=1))
        session.rollback.assert_called_once()


class TestItemRepositoryGetItems:
    """Tests for get_items."""

    def test_returns_list_when_items_found(self):
        session = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.id = 1
        mock_item2 = MagicMock()
        mock_item2.id = 2
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item1, mock_item2]
        session.execute = AsyncMock(return_value=mock_result)

        repo = ItemRepository(session)
        result = asyncio.run(repo.get_items(chat_id=123, limit=10))

        assert result == [mock_item1, mock_item2]
        session.execute.assert_called_once()

    def test_returns_empty_list_when_no_items(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ItemRepository(session)
        result = asyncio.run(repo.get_items(chat_id=456))

        assert result == []
        session.execute.assert_called_once()

    def test_raises_on_exception(self):
        session = MagicMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))

        repo = ItemRepository(session)
        with pytest.raises(Exception, match="DB error"):
            asyncio.run(repo.get_items(chat_id=1))


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
