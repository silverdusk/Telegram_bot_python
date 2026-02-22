"""Tests for app.services.bot_service."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

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
        assert "remove_item" in callback_data_list
        assert "Admin" in callback_data_list
        assert "availability_status" in callback_data_list
        assert "stop_bot" in callback_data_list


@patch("app.services.bot_service.get_settings")
class TestHandleRemoveItem:
    """Tests for handle_remove_item (start Remove flow)."""

    def test_sets_state_and_asks_for_item_name(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=123)
        update.effective_message = msg
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.handle_remove_item(update, context=mock_context, session=session))

        assert mock_context.user_data["state"] == "waiting_for_remove_item_name"
        msg.reply_text.assert_called_once()
        text = msg.reply_text.call_args[0][0]
        assert "remove" in text.lower() and "name" in text.lower()

    def test_does_nothing_when_no_effective_message(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        update = MagicMock()
        update.effective_chat = MagicMock(id=123)
        update.effective_message = None
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.handle_remove_item(update, context=mock_context, session=session))

        assert mock_context.user_data.get("state") != "waiting_for_remove_item_name"


@patch("app.services.bot_service.validate_text_input", return_value=True)
@patch("app.services.bot_service.get_settings")
class TestProcessRemoveItem:
    """Tests for process_remove_item (process name and delete)."""

    def test_replies_removed_count_when_items_deleted(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_remove_item_name"
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "  Widget  "
        session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.delete_by_name_and_chat = AsyncMock(return_value=2)
        with patch("app.services.bot_service.ItemRepository", return_value=mock_repo):
            service = BotService(mock_bot)
            asyncio.run(service.process_remove_item(update, context=mock_context, session=session))

        mock_repo.delete_by_name_and_chat.assert_called_once_with("Widget", 456)
        assert mock_context.user_data.get("state") is None
        msg.reply_text.assert_called_once()
        assert "Removed 2 item(s)" in msg.reply_text.call_args[0][0]

    def test_replies_not_found_when_zero_deleted(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_remove_item_name"
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "NoSuchItem"
        session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.delete_by_name_and_chat = AsyncMock(return_value=0)
        with patch("app.services.bot_service.ItemRepository", return_value=mock_repo):
            service = BotService(mock_bot)
            asyncio.run(service.process_remove_item(update, context=mock_context, session=session))

        msg.reply_text.assert_called_once()
        assert "No items found" in msg.reply_text.call_args[0][0]

    def test_replies_empty_name_error_when_text_stripped_empty(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_remove_item_name"
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "   "
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.process_remove_item(update, context=mock_context, session=session))

        msg.reply_text.assert_called_once()
        assert "empty" in msg.reply_text.call_args[0][0].lower()
        assert mock_context.user_data.get("state") == "waiting_for_remove_item_name"

    def test_replies_invalid_length_when_validation_fails(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        mock_validate.return_value = False
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_remove_item_name"
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "x" * 300
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.process_remove_item(update, context=mock_context, session=session))

        msg.reply_text.assert_called_once()
        assert "Invalid" in msg.reply_text.call_args[0][0] or "Length" in msg.reply_text.call_args[0][0]
        assert mock_context.user_data.get("state") == "waiting_for_remove_item_name"

    def test_does_nothing_when_state_not_remove(self, get_settings, mock_validate, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_item_name"
        msg = MagicMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "Widget"
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.process_remove_item(update, context=mock_context, session=session))

        msg.reply_text.assert_not_called()
