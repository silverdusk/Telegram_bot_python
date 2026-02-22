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
        mock_context.user_data["update_item_id"] = 42
        mock_context.user_data["update_data"] = {"item_name": "x"}
        mock_context.user_data["other"] = "keep"

        clear_flow_state(mock_context)

        assert "state" not in mock_context.user_data
        assert "item_data" not in mock_context.user_data
        assert "availability_item_name" not in mock_context.user_data
        assert "update_item_id" not in mock_context.user_data
        assert "update_data" not in mock_context.user_data
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
        assert "update_item" in callback_data_list
        assert "Admin" in callback_data_list
        assert "availability_status" in callback_data_list
        assert "stop_bot" in callback_data_list

    def test_update_field_keyboard_has_expected_buttons(self, get_settings, mock_settings, mock_bot):
        get_settings.return_value = mock_settings
        service = BotService(mock_bot)
        keyboard = service._update_field_keyboard()
        assert keyboard is not None
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        callback_data_list = [btn.callback_data for btn in all_buttons]
        assert "update_field_name" in callback_data_list
        assert "update_field_amount" in callback_data_list
        assert "update_field_type" in callback_data_list
        assert "update_field_price" in callback_data_list
        assert "update_field_availability" in callback_data_list
        assert "update_field_done" in callback_data_list


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


@patch("app.services.bot_service.get_settings")
class TestHandleUpdateItem:
    """Tests for handle_update_item (start Update flow)."""

    def test_sets_state_and_asks_for_item_name(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=123)
        update.effective_message = msg
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.handle_update_item(update, context=mock_context, session=session))

        assert mock_context.user_data["state"] == "waiting_for_update_item_name"
        assert mock_context.user_data.get("update_data") == {}
        msg.reply_text.assert_called_once()
        text = msg.reply_text.call_args[0][0]
        assert "update" in text.lower() and "name" in text.lower()

    def test_does_nothing_when_no_effective_message(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        update = MagicMock()
        update.effective_chat = MagicMock(id=123)
        update.effective_message = None
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.handle_update_item(update, context=mock_context, session=session))

        assert mock_context.user_data.get("state") != "waiting_for_update_item_name"


@patch("app.services.bot_service.validate_text_input", return_value=True)
@patch("app.services.bot_service.get_settings")
class TestProcessUpdateItem:
    """Tests for process_update_item."""

    def test_finds_one_item_and_shows_field_keyboard(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_item_name"
        mock_context.user_data["update_data"] = {}
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "  Widget  "
        session = MagicMock()
        mock_item = MagicMock()
        mock_item.id = 99
        mock_item.item_name = "Widget"
        mock_repo = MagicMock()
        mock_repo.get_items = AsyncMock(return_value=[mock_item])
        with patch("app.services.bot_service.ItemRepository", return_value=mock_repo):
            service = BotService(mock_bot)
            asyncio.run(service.process_update_item(update, context=mock_context, session=session))

        mock_repo.get_items.assert_called_once()
        assert mock_context.user_data["update_item_id"] == 99
        assert mock_context.user_data["state"] == "waiting_for_update_field"
        msg.reply_text.assert_called_once()
        assert "What do you want to change" in msg.reply_text.call_args[0][0] or "Done" in msg.reply_text.call_args[0][0]

    def test_replies_no_item_found_when_empty_list(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_item_name"
        mock_context.user_data["update_data"] = {}
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "NoSuch"
        session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_items = AsyncMock(return_value=[])
        with patch("app.services.bot_service.ItemRepository", return_value=mock_repo):
            service = BotService(mock_bot)
            asyncio.run(service.process_update_item(update, context=mock_context, session=session))

        msg.reply_text.assert_called_once()
        assert "No item found" in msg.reply_text.call_args[0][0]
        assert mock_context.user_data.get("update_item_id") is None
        assert mock_context.user_data.get("state") is None

    def test_replies_multiple_items_when_more_than_one(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_item_name"
        mock_context.user_data["update_data"] = {}
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "Dup"
        session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_items = AsyncMock(return_value=[MagicMock(id=1, item_name="Dup"), MagicMock(id=2, item_name="Dup")])
        with patch("app.services.bot_service.ItemRepository", return_value=mock_repo):
            service = BotService(mock_bot)
            asyncio.run(service.process_update_item(update, context=mock_context, session=session))

        msg.reply_text.assert_called_once()
        assert "Multiple" in msg.reply_text.call_args[0][0]
        assert mock_context.user_data.get("update_item_id") is None

    def test_waiting_for_update_field_replies_use_buttons(
        self, get_settings, mock_validate, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_field"
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "some text"
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.process_update_item(update, context=mock_context, session=session))

        msg.reply_text.assert_called_once()
        assert "buttons" in msg.reply_text.call_args[0][0].lower() or "Done" in msg.reply_text.call_args[0][0]

    def test_does_nothing_when_state_not_update(self, get_settings, mock_validate, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_item_name"
        msg = MagicMock()
        update = MagicMock()
        update.effective_chat = MagicMock(id=456)
        update.message = msg
        update.message.text = "Widget"
        session = MagicMock()

        service = BotService(mock_bot)
        asyncio.run(service.process_update_item(update, context=mock_context, session=session))

        msg.reply_text.assert_not_called()


@patch("app.services.bot_service.get_settings")
class TestApplyUpdateFieldChoice:
    """Tests for apply_update_field_choice (callback: Done, field buttons)."""

    def test_done_with_update_data_calls_repo_and_clears_state(
        self, get_settings, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_field"
        mock_context.user_data["update_item_id"] = 10
        mock_context.user_data["update_data"] = {"item_name": "NewName"}
        session = MagicMock()
        mock_updated = MagicMock()
        mock_updated.item_name = "NewName"
        mock_updated.item_amount = 2
        mock_updated.item_type = "spare part"
        mock_updated.item_price = 1.5
        mock_updated.availability = True
        mock_repo = MagicMock()
        mock_repo.update_item = AsyncMock(return_value=mock_updated)
        with patch("app.services.bot_service.ItemRepository", return_value=mock_repo):
            service = BotService(mock_bot)
            service.bot.send_message = AsyncMock()
            asyncio.run(service.apply_update_field_choice(
                mock_context, session, chat_id=789, callback_data="update_field_done"
            ))

        mock_repo.update_item.assert_called_once()
        call_args = mock_repo.update_item.call_args[0]
        assert call_args[0] == 10
        assert call_args[1].item_name == "NewName"
        assert mock_context.user_data.get("state") is None
        assert mock_context.user_data.get("update_item_id") is None
        service.bot.send_message.assert_called()
        msg_text = service.bot.send_message.call_args[0][1]
        assert "Item updated" in msg_text or "NewName" in msg_text

    def test_done_with_no_update_data_sends_no_changes(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_field"
        mock_context.user_data["update_item_id"] = 10
        mock_context.user_data["update_data"] = {}
        session = MagicMock()
        service = BotService(mock_bot)
        service.bot.send_message = AsyncMock()
        asyncio.run(service.apply_update_field_choice(
            mock_context, session, chat_id=789, callback_data="update_field_done"
        ))

        service.bot.send_message.assert_called()
        all_msg_texts = [c[0][1] for c in service.bot.send_message.call_args_list]
        assert any("No changes" in t for t in all_msg_texts)
        assert mock_context.user_data.get("state") == "waiting_for_update_field"

    def test_done_expired_when_no_update_item_id(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_field"
        mock_context.user_data["update_item_id"] = None
        mock_context.user_data["update_data"] = {"item_name": "X"}
        session = MagicMock()
        service = BotService(mock_bot)
        service.bot.send_message = AsyncMock()
        asyncio.run(service.apply_update_field_choice(
            mock_context, session, chat_id=789, callback_data="update_field_done"
        ))

        service.bot.send_message.assert_called_once()
        assert "expired" in service.bot.send_message.call_args[0][1].lower() or "start over" in service.bot.send_message.call_args[0][1].lower()
        assert mock_context.user_data.get("update_item_id") is None

    def test_field_name_sets_state_and_asks_for_value(self, get_settings, mock_settings, mock_bot, mock_context):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_field"
        mock_context.user_data["update_item_id"] = 5
        mock_context.user_data["update_data"] = {}
        session = MagicMock()
        service = BotService(mock_bot)
        service.bot.send_message = AsyncMock()
        asyncio.run(service.apply_update_field_choice(
            mock_context, session, chat_id=789, callback_data="update_field_name"
        ))

        assert mock_context.user_data["state"] == "waiting_for_update_name"
        service.bot.send_message.assert_called_once()
        assert "name" in service.bot.send_message.call_args[0][1].lower()

    def test_field_availability_yes_stores_and_returns_to_field_keyboard(
        self, get_settings, mock_settings, mock_bot, mock_context
    ):
        get_settings.return_value = mock_settings
        mock_context.user_data["state"] = "waiting_for_update_field"
        mock_context.user_data["update_data"] = {}
        session = MagicMock()
        service = BotService(mock_bot)
        service.bot.send_message = AsyncMock()
        asyncio.run(service.apply_update_field_choice(
            mock_context, session, chat_id=789, callback_data="update_field_availability_yes"
        ))

        assert mock_context.user_data["update_data"]["availability"] is True
        assert mock_context.user_data["state"] == "waiting_for_update_field"
        service.bot.send_message.assert_called_once()
        assert "Yes" in service.bot.send_message.call_args[0][1] or "else" in service.bot.send_message.call_args[0][1]
