"""Tests for app.schemas.item."""
import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from app.schemas.item import ItemCreate, ItemUpdate


@patch("app.core.config.get_settings")
class TestItemCreate:
    """Tests for ItemCreate schema."""

    def test_valid_spare_part(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part", "miscellaneous"]
        get_settings.return_value = mock_settings
        item = ItemCreate(
            item_name="Widget",
            item_amount=10,
            item_type="spare part",
            item_price=1.5,
            availability=True,
        )
        assert item.item_name == "Widget"
        assert item.item_amount == 10
        assert item.item_type == "spare part"
        assert item.item_price == 1.5
        assert item.availability is True

    def test_valid_miscellaneous(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part", "miscellaneous"]
        get_settings.return_value = mock_settings
        item = ItemCreate(
            item_name="Thing",
            item_amount=1,
            item_type="miscellaneous",
            availability=False,
        )
        assert item.item_type == "miscellaneous"
        assert item.item_price is None

    def test_item_type_case_insensitive(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part", "miscellaneous"]
        get_settings.return_value = mock_settings
        item = ItemCreate(
            item_name="X",
            item_amount=1,
            item_type="Spare Part",
            availability=False,
        )
        assert item.item_type == "spare part"

    def test_rejects_invalid_item_type(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part", "miscellaneous"]
        get_settings.return_value = mock_settings
        with pytest.raises(ValidationError) as exc_info:
            ItemCreate(
                item_name="X",
                item_amount=1,
                item_type="invalid",
                availability=False,
            )
        assert "item_type" in str(exc_info.value).lower() or "Item type" in str(exc_info.value)

    def test_rejects_zero_amount(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part"]
        get_settings.return_value = mock_settings
        with pytest.raises(ValidationError):
            ItemCreate(
                item_name="X",
                item_amount=0,
                item_type="spare part",
                availability=False,
            )

    def test_rejects_negative_price(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part"]
        get_settings.return_value = mock_settings
        with pytest.raises(ValidationError):
            ItemCreate(
                item_name="X",
                item_amount=1,
                item_type="spare part",
                item_price=-1.0,
                availability=False,
            )

    def test_rejects_empty_item_name(self, get_settings, mock_settings):
        mock_settings.allowed_types = ["spare part"]
        get_settings.return_value = mock_settings
        with pytest.raises(ValidationError):
            ItemCreate(
                item_name="",
                item_amount=1,
                item_type="spare part",
                availability=False,
            )


class TestItemUpdate:
    """Tests for ItemUpdate schema (optional fields)."""

    def test_all_optional(self):
        u = ItemUpdate()
        assert u.item_name is None
        assert u.item_amount is None
        assert u.item_type is None
        assert u.item_price is None
        assert u.availability is None

    def test_partial_update(self):
        u = ItemUpdate(item_amount=5)
        assert u.item_amount == 5
        assert u.item_name is None
