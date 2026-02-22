"""Tests for app.services.bot_service."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.bot_service import clear_flow_state, BotService


class TestClearFlowState:
    """Tests for clear_flow_state."""

    def test_clears_all_flow_keys(self, mock_context):
        mock_context.user_data["state"] = "waiting_for_item_name"
        mock_context.user_data["item_data"] = {"x": 1}
        mock_context.user_data["availability_item_name"] = "FOO"
        mock_context.user_data["other"] = "keep"

        clear_flow_state(mock_context)

        assert "state" not in mock_context.user_data
        assert "item_data" not in mock_context.user_data
        assert "availability_item_name" not in mock_context.user_data
        assert mock_context.user_data["other"] == "keep"

    def test_idempotent_when_keys_missing(self, mock_context):
        mock_context.user_data["other"] = "keep"
        clear_flow_state(mock_context)
        assert mock_context.user_data["other"] == "keep"


@patch("app.services.bot_service.get_settings")
class TestBotServiceKeyboards:
    """Tests for BotService keyboard builders."""

    def test_item_type_keyboard_has_buttons_for_allowed_types(self, get_settings, mock_settings, mock_bot):
        get_settings.return_value = mock_settings
        service = BotService(mock_bot)
        keyboard = service._item_type_keyboard()
        assert keyboard is not None
        # InlineKeyboardMarkup has inline_keyboard: tuple of rows
        rows = keyboard.inline_keyboard
        assert len(rows) >= 1
        all_buttons = [btn for row in rows for btn in row]
        callback_data_list = [btn.callback_data for btn in all_buttons]
        assert "item_type_spare part" in callback_data_list
        assert "item_type_miscellaneous" in callback_data_list

    def test_menu_inline_keyboard_has_main_actions(self, get_settings, mock_settings, mock_bot):
        get_settings.return_value = mock_settings
        service = BotService(mock_bot)
        keyboard = service._menu_inline_keyboard()
        assert keyboard is not None
        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        callback_data_list = [btn.callback_data for btn in all_buttons]
        assert "Get" in callback_data_list
        assert "Add" in callback_data_list
        assert "Admin" in callback_data_list
        assert "availability_status" in callback_data_list
        assert "stop_bot" in callback_data_list
