"""Tests for app.database.repository (ItemRepository)."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.database.repository import ItemRepository


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
