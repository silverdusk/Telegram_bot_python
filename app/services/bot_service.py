"""Telegram bot service for handling bot logic."""
import logging
from typing import Optional
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repository import ItemRepository, UserRepository
from app.schemas.item import ItemCreate, ItemUpdate
from app.core.validators import (
    validate_text_input,
    is_int,
    is_float,
    check_working_hours,
)
from app.core.config import get_settings
from app.core.permissions import get_user_role, is_admin_role, can_manage_item

logger = logging.getLogger(__name__)


def clear_flow_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear any ongoing flow state so user starts from a clean slate."""
    for key in (
        'state', 'item_data', 'availability_item_name', 'update_item_id', 'update_data',
        'update_user_id', 'manage_add_telegram_id', 'manage_set_role_telegram_id',
    ):
        context.user_data.pop(key, None)


class BotService:
    """Service for handling Telegram bot operations."""

    def __init__(self, bot: Bot):
        """Initialize bot service."""
        self.bot = bot
        self.settings = get_settings()

    async def send_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message with keyboard. Ensures user exists in DB (role user) if not fallback admin."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        user_id = update.effective_user.id if update.effective_user else None
        session = context.bot_data.get("current_db_session") if context.bot_data else None
        if session and user_id is not None and user_id not in self.settings.effective_fallback_admin_ids:
            try:
                user_repo = UserRepository(session)
                if await user_repo.get_by_telegram_id(user_id) is None:
                    await user_repo.create_user(user_id, "user")
                    logger.info("Created user for telegram_user_id=%s", user_id)
            except Exception as e:
                logger.warning("Could not ensure user for telegram_user_id=%s: %s", user_id, e)
        logger.info("Command /start chat_id=%s", chat_id)
        keyboard = [
            [KeyboardButton('Get'), KeyboardButton('Add')],
            [KeyboardButton('Remove item'), KeyboardButton('Update item')],
            [KeyboardButton('Admin'), KeyboardButton('Send test message')],
            [KeyboardButton('Change availability status')],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        msg = update.effective_message
        if msg:
            await msg.reply_text(
                "Hi! :)\nI'm organizer bot. I will help you to add your items.\n"
                "You can also use /menu for the same actions in a compact menu.",
                reply_markup=reply_markup,
            )
        logger.info("Welcome message sent chat_id=%s", chat_id)

    async def send_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send menu with inline keyboard."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        logger.info("Command /menu chat_id=%s", chat_id)
        reply_markup = self._menu_inline_keyboard()
        msg = update.effective_message
        if msg:
            await msg.reply_text(
                'What you want to do?',
                reply_markup=reply_markup,
            )
        logger.info("Menu sent chat_id=%s", chat_id)

    async def handle_add_item(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Handle add item command."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        logger.info("Add item flow started chat_id=%s", chat_id)
        msg = update.effective_message
        if not msg:
            return
        if not check_working_hours():
            await msg.reply_text(
                'You are trying to send request outside of working hours - please try again later.'
            )
            logger.info("Add item rejected (outside working hours) chat_id=%s", chat_id)
            return

        # Store state for multi-step input
        context.user_data['state'] = 'waiting_for_item_name'
        context.user_data['item_data'] = {}

        await msg.reply_text(
            'Please provide name of item.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )

    async def process_item_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> Optional[ItemCreate]:
        """Process multi-step item input."""
        state = context.user_data.get('state')
        item_data = context.user_data.get('item_data', {})
        
        if state == 'waiting_for_item_name':
            raw = update.message.text
            if raw is None:
                return None
            name = raw.strip()
            if not name:
                await update.message.reply_text(
                    'Item name cannot be empty.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None
            min_len = self.settings.min_len_str
            max_len = self.settings.max_len_str
            if not validate_text_input(name, min_len=min_len, max_len=max_len):
                await update.message.reply_text(
                    f'Invalid name. Use letters, numbers, or common symbols. '
                    f'Length must be between {min_len} and {max_len} characters.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None

            item_data['item_name'] = name
            if update.effective_user:
                context.user_data['_add_item_user_id'] = update.effective_user.id
            context.user_data['state'] = 'waiting_for_item_amount'
            await update.message.reply_text(
                'Please provide amount of items.\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
            return None

        elif state == 'waiting_for_item_amount':
            raw_amount = update.message.text
            if not is_int(raw_amount):
                await update.message.reply_text(
                    'Invalid amount. Please enter a whole number.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None
            amount = int(raw_amount)
            max_amount = self.settings.max_item_amount
            if amount < 1:
                await update.message.reply_text(
                    'Amount must be at least 1.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None
            if amount > max_amount:
                await update.message.reply_text(
                    f'Amount must be at most {max_amount:,}.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None

            item_data['item_amount'] = amount
            context.user_data['state'] = 'waiting_for_item_type'
            type_buttons = self._item_type_keyboard()
            await update.message.reply_text(
                'Please choose item type.\nOr /cancel to cancel.',
                reply_markup=type_buttons,
            )
            return None

        elif state == 'waiting_for_item_type':
            item_type = update.message.text.lower()
            if item_type not in [t.lower() for t in self.settings.allowed_types]:
                allowed = " or ".join(self.settings.allowed_types)
                await update.message.reply_text(
                    f'Invalid type. Allowed: {allowed}. Please choose below or type again:',
                    reply_markup=self._item_type_keyboard(),
                )
                return None

            item_data['item_type'] = item_type
            context.user_data['state'] = 'waiting_for_item_price'
            await update.message.reply_text(
                'Please provide item price value.\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
            return None

        elif state == 'waiting_for_item_price':
            raw_price = update.message.text
            if not is_float(raw_price):
                await update.message.reply_text(
                    'Invalid price. Please enter a number.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None
            price = round(float(raw_price), 2)
            max_price = self.settings.max_item_price
            if price < 0:
                await update.message.reply_text(
                    'Price cannot be negative.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None
            if price > max_price:
                await update.message.reply_text(
                    f'Price must be at most {max_price:,.2f}.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None

            item_data['item_price'] = price
            context.user_data['state'] = 'waiting_for_availability'
            avail_buttons = InlineKeyboardMarkup.from_row([
                InlineKeyboardButton('Yes', callback_data='item_availability_yes'),
                InlineKeyboardButton('No', callback_data='item_availability_no'),
            ])
            await update.message.reply_text(
                'Is this item available?\nOr /cancel to cancel.',
                reply_markup=avail_buttons,
            )
            return None
        
        elif state == 'waiting_for_availability':
            availability_text = update.message.text.lower()
            if availability_text not in ['yes', 'no']:
                avail_buttons = InlineKeyboardMarkup.from_row([
                    InlineKeyboardButton('Yes', callback_data='item_availability_yes'),
                    InlineKeyboardButton('No', callback_data='item_availability_no'),
                ])
                await update.message.reply_text(
                    'Please choose Yes or No:',
                    reply_markup=avail_buttons,
                )
                return None

            item_data['availability'] = availability_text == 'yes'

        # Create item (shared path for text and button choice)
        if session is None:
            await update.message.reply_text("Database session not available. Please try again.")
            return None
        chat_id = update.effective_chat.id if update.effective_chat else None
        return await self._finish_add_item(context, session, chat_id, user_id=update.effective_user.id if update.effective_user else None)

    def _item_type_keyboard(self) -> InlineKeyboardMarkup:
        """Inline keyboard for item type choice (fixed options)."""
        buttons = [
            InlineKeyboardButton(t, callback_data=f'item_type_{t}')
            for t in self.settings.allowed_types
        ]
        return InlineKeyboardMarkup.from_row(buttons)

    async def advance_after_item_type(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
        item_type: str,
    ) -> None:
        """Continue Add flow after user chose item type via button. Sends next prompt."""
        context.user_data['item_data'] = context.user_data.get('item_data', {})
        context.user_data['item_data']['item_type'] = item_type.lower()
        context.user_data['state'] = 'waiting_for_item_price'
        await self.bot.send_message(
            chat_id,
            'Please provide item price value:',
            reply_markup=ForceReply(selective=True),
        )

    async def _finish_add_item(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[ItemCreate]:
        """Create item from context.user_data['item_data'], clear state, send confirmation."""
        if session is None:
            await self.bot.send_message(chat_id, "Database session not available. Please try again.")
            return None
        item_data = context.user_data.get('item_data', {})
        if not item_data:
            await self.bot.send_message(chat_id, "No item data. Please start over with Add.")
            return None
        try:
            item_create = ItemCreate(**item_data)
            repository = ItemRepository(session)
            creator = user_id if user_id is not None else context.user_data.get("_add_item_user_id")
            item = await repository.create_item(item_create, chat_id, created_by_user_id=creator)
            context.user_data.pop('state', None)
            context.user_data.pop('item_data', None)
            text = (
                f'Request is placed for processing:\n'
                f'Item name: {item.item_name}\n'
                f'Amount of items: {item.item_amount}\n'
                f'Item type: {item.item_type}\n'
            )
            if item.item_type == 'spare part':
                text += f'Item price: {item.item_price}\n'
                text += f'Availability: {item.availability}\n'
            await self.bot.send_message(chat_id, text)
            logger.info("Item created id=%s chat_id=%s", item.id, chat_id)
            # Offer to add another or go back to menu
            next_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton('Add another item', callback_data='add_another')],
                [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
            ])
            await self.bot.send_message(
                chat_id,
                'What would you like to do next?',
                reply_markup=next_keyboard,
            )
            return item_create
        except Exception as e:
            logger.error("Error creating item: %s", type(e).__name__, exc_info=True)
            await self.bot.send_message(chat_id, "Failed to process the request. Please try again later.")
            return None

    async def start_update_item_flow(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Update item flow from a chat (e.g. after 'Update another item' callback)."""
        clear_flow_state(context)
        context.user_data['state'] = 'waiting_for_update_item_name'
        context.user_data['update_data'] = {}
        await self.bot.send_message(
            chat_id,
            'Please provide the exact name of the item to update.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Update item flow started (another) chat_id=%s", chat_id)

    async def start_add_item_flow(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Add item flow from a chat (e.g. after 'Add another item' callback)."""
        if not check_working_hours():
            await self.bot.send_message(
                chat_id,
                'You are trying to send request outside of working hours - please try again later.',
            )
            return
        context.user_data['state'] = 'waiting_for_item_name'
        context.user_data['item_data'] = {}
        await self.bot.send_message(
            chat_id,
            'Please provide name of item.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )

    def _menu_inline_keyboard(self) -> InlineKeyboardMarkup:
        """Build the main menu inline keyboard (shared by send_menu and send_menu_to_chat)."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Get', callback_data='Get'),
                InlineKeyboardButton('Add', callback_data='Add'),
            ],
            [InlineKeyboardButton('Remove item', callback_data='remove_item')],
            [InlineKeyboardButton('Update item', callback_data='update_item')],
            [
                InlineKeyboardButton('Admin', callback_data='Admin'),
                InlineKeyboardButton('Change availability status', callback_data='availability_status'),
            ],
            [
                InlineKeyboardButton('Send test message', callback_data='Send test message'),
                InlineKeyboardButton('Stop', callback_data='stop_bot'),
            ],
        ])

    async def send_menu_to_chat(self, chat_id: int) -> None:
        """Send the main menu inline keyboard to a chat (e.g. after 'Back to menu')."""
        await self.bot.send_message(
            chat_id,
            'What you want to do?',
            reply_markup=self._menu_inline_keyboard(),
        )

    async def get_items(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Get items from database."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        if session is None:
            await msg.reply_text("Database session not available. Please try again.")
            logger.warning("Get items: no db session chat_id=%s", chat_id)
            return

        logger.info("Get items requested chat_id=%s", chat_id)
        try:
            repository = ItemRepository(session)
            items = await repository.get_items(chat_id=chat_id, limit=50)

            if items:
                item_info = "\n".join([
                    f"Item: {item.item_name}, Amount: {item.item_amount}"
                    for item in items
                ])
                await msg.reply_text(f"Items in the database:\n{item_info}")
                logger.info("Get items returned count=%s chat_id=%s", len(items), chat_id)
            else:
                await msg.reply_text("No items found in the database.")
                logger.info("Get items returned empty chat_id=%s", chat_id)
            await msg.reply_text(
                'What would you like to do next?',
                reply_markup=self._back_to_menu_keyboard(),
            )
        except Exception as e:
            logger.error("Error getting items: %s", type(e).__name__, exc_info=True)
            await msg.reply_text("An error occurred. Please try again later.")
            await msg.reply_text(
                'What would you like to do next?',
                reply_markup=self._back_to_menu_keyboard(),
            )

    async def start_remove_item_flow(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Remove item flow from chat (e.g. after 'Remove another item' callback)."""
        clear_flow_state(context)
        context.user_data['state'] = 'waiting_for_remove_item_name'
        await self.bot.send_message(
            chat_id,
            'Please provide the name of the item to remove.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Remove item flow started (another) chat_id=%s", chat_id)

    async def handle_remove_item(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Start Remove item flow: ask for item name."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        logger.info("Remove item flow started chat_id=%s", chat_id)
        context.user_data['state'] = 'waiting_for_remove_item_name'
        await msg.reply_text(
            'Please provide the name of the item to remove.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )

    async def process_remove_item(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Process item name and delete matching items for this chat."""
        state = context.user_data.get('state')
        if state != 'waiting_for_remove_item_name':
            return
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not update.message or not update.message.text or session is None or not chat_id:
            return
        raw = update.message.text.strip()
        if not raw:
            await update.message.reply_text(
                'Item name cannot be empty.\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
            return
        min_len = self.settings.min_len_str
        max_len = self.settings.max_len_str
        if not validate_text_input(raw, min_len=min_len, max_len=max_len):
            await update.message.reply_text(
                f'Invalid name. Length must be between {min_len} and {max_len} characters.\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            role = await get_user_role(user_id, session, self.settings) if session else None
            repository = ItemRepository(session)
            creator_filter = None if is_admin_role(role) else user_id
            deleted = await repository.delete_by_name_and_chat(raw, chat_id, created_by_user_id=creator_filter)
            context.user_data.pop('state', None)
            if deleted > 0:
                await update.message.reply_text(
                    f'Removed {deleted} item(s) named "{raw}".'
                )
                logger.info("Remove item: deleted=%s chat_id=%s name=%s", deleted, chat_id, raw)
            else:
                await update.message.reply_text(f'No items found with that name ("{raw}").')
                logger.info("Remove item: none found chat_id=%s name=%s", chat_id, raw)
            next_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton('Remove another item', callback_data='remove_another_item')],
                [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
            ])
            await update.message.reply_text(
                'What would you like to do next?',
                reply_markup=next_keyboard,
            )
        except Exception as e:
            logger.error("Error removing item: %s", type(e).__name__, exc_info=True)
            await update.message.reply_text("An error occurred. Please try again later.")
            await update.message.reply_text(
                'What would you like to do next?',
                reply_markup=self._back_to_menu_keyboard(),
            )

    def _back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Single 'Back to menu' button (for end of flows)."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
        ])

    def _admin_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Admin menu: manage users and back."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton('List users', callback_data='mu_list')],
            [
                InlineKeyboardButton('Add user', callback_data='mu_add'),
                InlineKeyboardButton('Set role', callback_data='mu_set_role'),
            ],
            [InlineKeyboardButton('Remove user', callback_data='mu_remove')],
            [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
        ])

    def _manage_role_keyboard(self) -> InlineKeyboardMarkup:
        """Choose role for Add user / Set role flows."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('admin', callback_data='mu_add_role_admin'),
                InlineKeyboardButton('user', callback_data='mu_add_role_user'),
            ],
        ])

    def _manage_set_role_choice_keyboard(self) -> InlineKeyboardMarkup:
        """Choose role for Set role flow (different callback prefix to distinguish)."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('admin', callback_data='mu_set_role_admin'),
                InlineKeyboardButton('user', callback_data='mu_set_role_user'),
            ],
        ])

    def _update_field_keyboard(self) -> InlineKeyboardMarkup:
        """Inline keyboard for choosing which field to update or Done."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton('Name', callback_data='update_field_name'),
                InlineKeyboardButton('Amount', callback_data='update_field_amount'),
            ],
            [
                InlineKeyboardButton('Type', callback_data='update_field_type'),
                InlineKeyboardButton('Price', callback_data='update_field_price'),
            ],
            [
                InlineKeyboardButton('Availability', callback_data='update_field_availability'),
                InlineKeyboardButton('Done', callback_data='update_field_done'),
            ],
        ])

    async def handle_update_item(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Start Update item flow: ask for item name."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        logger.info("Update item flow started chat_id=%s", chat_id)
        context.user_data['state'] = 'waiting_for_update_item_name'
        context.user_data['update_data'] = {}
        await msg.reply_text(
            'Please provide the exact name of the item to update.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )

    async def process_update_item(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Process update-item flow: item name, then field values."""
        state = context.user_data.get('state')
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not update.message or not update.message.text or session is None or not chat_id:
            return

        if state == 'waiting_for_update_item_name':
            raw = update.message.text.strip()
            if not raw:
                await update.message.reply_text(
                    'Item name cannot be empty.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            min_len = self.settings.min_len_str
            max_len = self.settings.max_len_str
            if not validate_text_input(raw, min_len=min_len, max_len=max_len):
                await update.message.reply_text(
                    f'Invalid name. Length must be between {min_len} and {max_len} characters.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            try:
                repository = ItemRepository(session)
                items = await repository.get_items(chat_id=chat_id, item_name=raw, limit=20)
                exact = [i for i in items if i.item_name.strip().lower() == raw.strip().lower()]
                if not exact:
                    await update.message.reply_text(f'No item found with that name ("{raw}").')
                    context.user_data.pop('state', None)
                    context.user_data.pop('update_data', None)
                    return
                if len(exact) > 1:
                    await update.message.reply_text(
                        f'Multiple items with that name. Please remove duplicates or use a more specific name.'
                    )
                    context.user_data.pop('state', None)
                    context.user_data.pop('update_data', None)
                    return
                item = exact[0]
                user_id = update.effective_user.id if update.effective_user else None
                role = await get_user_role(user_id, session, self.settings)
                if not can_manage_item(item.created_by_user_id, user_id, role):
                    await update.message.reply_text("You are not authorized to update this item.")
                    context.user_data.pop('state', None)
                    context.user_data.pop('update_data', None)
                    return
                context.user_data['update_item_id'] = item.id
                context.user_data['update_user_id'] = user_id
                context.user_data['state'] = 'waiting_for_update_field'
                await update.message.reply_text(
                    'What do you want to change? Choose a field or tap Done to save.',
                    reply_markup=self._update_field_keyboard(),
                )
            except Exception as e:
                logger.error("Error in update item (find): %s", type(e).__name__, exc_info=True)
                await update.message.reply_text("An error occurred. Please try again later.")

        elif state == 'waiting_for_update_field':
            await update.message.reply_text(
                'Please use the buttons below to choose a field to change, or tap Done.',
                reply_markup=self._update_field_keyboard(),
            )

        elif state == 'waiting_for_update_name':
            raw = update.message.text.strip()
            if not raw:
                await update.message.reply_text(
                    'Item name cannot be empty.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            if not validate_text_input(raw, min_len=self.settings.min_len_str, max_len=self.settings.max_len_str):
                await update.message.reply_text(
                    f'Invalid name. Length must be between {self.settings.min_len_str} and {self.settings.max_len_str} characters.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            context.user_data.setdefault('update_data', {})['item_name'] = raw
            context.user_data['state'] = 'waiting_for_update_field'
            await update.message.reply_text('Updated. What else?', reply_markup=self._update_field_keyboard())

        elif state == 'waiting_for_update_amount':
            raw = update.message.text.strip()
            if not is_int(raw):
                await update.message.reply_text(
                    'Please enter a whole number for amount.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            val = int(raw)
            if val < 1 or val > self.settings.max_item_amount:
                await update.message.reply_text(
                    f'Amount must be between 1 and {self.settings.max_item_amount}.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            context.user_data.setdefault('update_data', {})['item_amount'] = val
            context.user_data['state'] = 'waiting_for_update_field'
            await update.message.reply_text('Updated. What else?', reply_markup=self._update_field_keyboard())

        elif state == 'waiting_for_update_type':
            raw = update.message.text.strip().lower()
            if raw not in [t.lower() for t in self.settings.allowed_types]:
                allowed = ', '.join(self.settings.allowed_types)
                await update.message.reply_text(
                    f'Type must be one of: {allowed}.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            context.user_data.setdefault('update_data', {})['item_type'] = raw
            context.user_data['state'] = 'waiting_for_update_field'
            await update.message.reply_text('Updated. What else?', reply_markup=self._update_field_keyboard())

        elif state == 'waiting_for_update_price':
            raw = update.message.text.strip()
            if not is_float(raw):
                await update.message.reply_text(
                    'Please enter a number for price.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            val = round(float(raw), 2)
            if val < 0 or val > self.settings.max_item_price:
                await update.message.reply_text(
                    f'Price must be between 0 and {self.settings.max_item_price}.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            context.user_data.setdefault('update_data', {})['item_price'] = val
            context.user_data['state'] = 'waiting_for_update_field'
            await update.message.reply_text('Updated. What else?', reply_markup=self._update_field_keyboard())

        elif state == 'waiting_for_update_availability':
            text = update.message.text.strip().upper()
            if text not in ('YES', 'NO'):
                btns = InlineKeyboardMarkup.from_row([
                    InlineKeyboardButton('Yes', callback_data='update_field_availability_yes'),
                    InlineKeyboardButton('No', callback_data='update_field_availability_no'),
                ])
                await update.message.reply_text(
                    'Please choose Yes or No for availability.\nOr /cancel to cancel.',
                    reply_markup=btns,
                )
                return
            context.user_data.setdefault('update_data', {})['availability'] = (text == 'YES')
            context.user_data['state'] = 'waiting_for_update_field'
            await update.message.reply_text('Updated. What else?', reply_markup=self._update_field_keyboard())

    async def apply_update_field_choice(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
        callback_data: str,
    ) -> None:
        """Handle callback: field chosen or Done in update-item flow."""
        state = context.user_data.get('state')
        if state != 'waiting_for_update_field' and not (state or '').startswith('waiting_for_update'):
            await self.bot.send_message(chat_id, "This action has expired. Please start over with Update item.")
            return
        if session is None:
            await self.bot.send_message(chat_id, "Database session not available. Please try again.")
            return

        if callback_data == 'update_field_done':
            update_item_id = context.user_data.get('update_item_id')
            update_data = context.user_data.get('update_data') or {}
            if update_item_id is None:
                await self.bot.send_message(chat_id, "Session expired. Please start over with Update item.")
                clear_flow_state(context)
                return
            if not update_data:
                await self.bot.send_message(chat_id, "No changes made. Item unchanged.")
                context.user_data['state'] = 'waiting_for_update_field'
                await self.bot.send_message(
                    chat_id,
                    'Choose a field to change or tap Done to finish.',
                    reply_markup=self._update_field_keyboard(),
                )
                return
            try:
                repository = ItemRepository(session)
                item_to_check = await repository.get_item_by_id(update_item_id)
                if not item_to_check:
                    await self.bot.send_message(chat_id, "Item not found. Please start over.")
                    clear_flow_state(context)
                    return
                user_id = context.user_data.get('update_user_id')
                role = await get_user_role(user_id, session, self.settings)
                if not can_manage_item(item_to_check.created_by_user_id, user_id, role):
                    await self.bot.send_message(chat_id, "You are not authorized to update this item.")
                    return
                payload = ItemUpdate(**update_data)
                updated = await repository.update_item(update_item_id, payload)
                clear_flow_state(context)
                if updated:
                    await self.bot.send_message(
                        chat_id,
                        f'Item updated: {updated.item_name}, amount={updated.item_amount}, '
                        f'type={updated.item_type}, price={updated.item_price}, availability={updated.availability}',
                    )
                    logger.info("Update item done id=%s chat_id=%s", update_item_id, chat_id)
                    next_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton('Update another item', callback_data='update_another_item')],
                        [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
                    ])
                    await self.bot.send_message(
                        chat_id,
                        'What would you like to do next?',
                        reply_markup=next_keyboard,
                    )
                else:
                    await self.bot.send_message(chat_id, "Item could not be updated. Please try again.")
            except Exception as e:
                logger.error("Error updating item: %s", type(e).__name__, exc_info=True)
                await self.bot.send_message(chat_id, "An error occurred. Please try again later.")
                context.user_data['state'] = 'waiting_for_update_field'

        elif callback_data == 'update_field_availability_yes':
            context.user_data.setdefault('update_data', {})['availability'] = True
            context.user_data['state'] = 'waiting_for_update_field'
            await self.bot.send_message(chat_id, 'Availability set to Yes. What else?', reply_markup=self._update_field_keyboard())
        elif callback_data == 'update_field_availability_no':
            context.user_data.setdefault('update_data', {})['availability'] = False
            context.user_data['state'] = 'waiting_for_update_field'
            await self.bot.send_message(chat_id, 'Availability set to No. What else?', reply_markup=self._update_field_keyboard())

        elif callback_data == 'update_field_name':
            context.user_data['state'] = 'waiting_for_update_name'
            await self.bot.send_message(
                chat_id,
                'Enter new name for the item.\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
        elif callback_data == 'update_field_amount':
            context.user_data['state'] = 'waiting_for_update_amount'
            await self.bot.send_message(
                chat_id,
                f'Enter new amount (1–{self.settings.max_item_amount}).\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
        elif callback_data == 'update_field_type':
            context.user_data['state'] = 'waiting_for_update_type'
            types_row = [
                InlineKeyboardButton(t, callback_data=f'update_field_type_{t}')
                for t in self.settings.allowed_types
            ]
            await self.bot.send_message(
                chat_id,
                'Choose new type or type it in the chat.\nOr /cancel to cancel.',
                reply_markup=InlineKeyboardMarkup([types_row]),
            )
        elif callback_data == 'update_field_price':
            context.user_data['state'] = 'waiting_for_update_price'
            await self.bot.send_message(
                chat_id,
                f'Enter new price (0–{self.settings.max_item_price}).\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
        elif callback_data == 'update_field_availability':
            context.user_data['state'] = 'waiting_for_update_availability'
            btns = InlineKeyboardMarkup.from_row([
                InlineKeyboardButton('Yes', callback_data='update_field_availability_yes'),
                InlineKeyboardButton('No', callback_data='update_field_availability_no'),
            ])
            await self.bot.send_message(
                chat_id,
                'Set availability.\nOr /cancel to cancel.',
                reply_markup=btns,
            )
        elif callback_data.startswith('update_field_type_'):
            chosen = callback_data.replace('update_field_type_', '', 1).strip()
            if chosen.lower() in [t.lower() for t in self.settings.allowed_types]:
                context.user_data.setdefault('update_data', {})['item_type'] = chosen.lower()
            context.user_data['state'] = 'waiting_for_update_field'
            await self.bot.send_message(chat_id, 'Updated. What else?', reply_markup=self._update_field_keyboard())

    async def start_availability_flow(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Change availability flow from chat (e.g. after 'Change availability status' again callback)."""
        clear_flow_state(context)
        context.user_data['state'] = 'waiting_for_availability_item_name'
        await self.bot.send_message(
            chat_id,
            'Please provide item name.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )
        logger.info("Availability update flow started (another) chat_id=%s", chat_id)

    async def update_availability_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Handle availability status update."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        logger.info("Availability update flow started chat_id=%s", chat_id)
        context.user_data['state'] = 'waiting_for_availability_item_name'
        await msg.reply_text(
            'Please provide item name.\nOr /cancel to cancel.',
            reply_markup=ForceReply(selective=True),
        )
    
    async def process_availability_update(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Process availability status update."""
        state = context.user_data.get('state')
        
        if state == 'waiting_for_availability_item_name':
            raw = update.message.text
            if raw is None:
                return
            item_name = raw.strip()
            if not item_name:
                await update.message.reply_text(
                    'Item name cannot be empty.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            min_len = self.settings.min_len_str
            max_len = self.settings.max_len_str
            if not validate_text_input(item_name, min_len=min_len, max_len=max_len):
                await update.message.reply_text(
                    f'Invalid name. Length must be between {min_len} and {max_len} characters.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return
            context.user_data['availability_item_name'] = item_name
            context.user_data['state'] = 'waiting_for_availability_status'
            status_buttons = InlineKeyboardMarkup.from_row([
                InlineKeyboardButton('YES', callback_data='avail_status_yes'),
                InlineKeyboardButton('NO', callback_data='avail_status_no'),
            ])
            await update.message.reply_text(
                'Set availability for this item.\nOr /cancel to cancel.',
                reply_markup=status_buttons,
            )

        elif state == 'waiting_for_availability_status':
            status_text = update.message.text.upper()
            item_name = context.user_data.get('availability_item_name')
            
            if status_text not in ['YES', 'NO']:
                status_buttons = InlineKeyboardMarkup.from_row([
                    InlineKeyboardButton('YES', callback_data='avail_status_yes'),
                    InlineKeyboardButton('NO', callback_data='avail_status_no'),
                ])
                await update.message.reply_text(
                    'Please choose YES or NO:',
                    reply_markup=status_buttons,
                )
                return

            availability = status_text == 'YES'

            if session is None:
                await update.message.reply_text("Database session not available. Please try again.")
                return
            
            try:
                user_id = update.effective_user.id if update.effective_user else None
                role = await get_user_role(user_id, session, self.settings)
                chat_id_av = update.effective_chat.id if update.effective_chat else None
                creator_filter = user_id if role == "user" else None
                repository = ItemRepository(session)
                updated = await repository.update_availability(
                    item_name, availability, chat_id=chat_id_av, created_by_user_id=creator_filter
                )
                if updated:
                    await update.message.reply_text(
                        f'Update availability status.\n'
                        f'Item {item_name}.\n'
                        f'Availability - {"available" if availability else "not available"}'
                    )
                    logger.info("Availability updated chat_id=%s", update.effective_chat.id)
                else:
                    await update.message.reply_text(f'Item {item_name} not found.')
                    logger.info("Availability update: item not found chat_id=%s", update.effective_chat.id)
                next_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton('Change availability status', callback_data='change_availability_again')],
                    [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
                ])
                await update.message.reply_text(
                    'What would you like to do next?',
                    reply_markup=next_keyboard,
                )
                # Clear state
                context.user_data.pop('state', None)
                context.user_data.pop('availability_item_name', None)
            except Exception as e:
                logger.error("Error updating availability: %s", type(e).__name__, exc_info=True)
                await update.message.reply_text("An error occurred. Please try again later.")

    async def apply_availability_status_choice(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
        availability: bool,
        user_id: Optional[int] = None,
    ) -> None:
        """Apply availability choice from Change availability flow (button)."""
        item_name = context.user_data.get('availability_item_name')
        if not item_name:
            await self.bot.send_message(chat_id, "Session expired. Please start over with Change availability status.")
            context.user_data.pop('state', None)
            context.user_data.pop('availability_item_name', None)
            return
        if session is None:
            await self.bot.send_message(chat_id, "Database session not available. Please try again.")
            return
        try:
            role = await get_user_role(user_id, session, self.settings)
            creator_filter = user_id if role == "user" else None
            repository = ItemRepository(session)
            updated = await repository.update_availability(
                item_name, availability, chat_id=chat_id, created_by_user_id=creator_filter
            )
            context.user_data.pop('state', None)
            context.user_data.pop('availability_item_name', None)
            if updated:
                await self.bot.send_message(
                    chat_id,
                    f'Availability updated.\nItem: {item_name}.\n'
                    f'Availability: {"available" if availability else "not available"}',
                )
                logger.info("Availability updated chat_id=%s", chat_id)
            else:
                await self.bot.send_message(chat_id, f'Item "{item_name}" not found.')
                logger.info("Availability update: item not found chat_id=%s", chat_id)
            next_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton('Change availability status', callback_data='change_availability_again')],
                [InlineKeyboardButton('Back to menu', callback_data='show_menu')],
            ])
            await self.bot.send_message(
                chat_id,
                'What would you like to do next?',
                reply_markup=next_keyboard,
            )
        except Exception as e:
            logger.error("Error updating availability: %s", type(e).__name__, exc_info=True)
            await self.bot.send_message(chat_id, "An error occurred. Please try again later.")
    
    async def send_test_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Send test/demo message (admin only)."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        if session is None:
            await msg.reply_text("Database session not available. Please try again.")
            return

        user_id = update.effective_user.id if update.effective_user else None
        role = await get_user_role(user_id, session, self.settings)
        if not is_admin_role(role):
            await msg.reply_text("You are not authorized to use this command.")
            logger.warning("Unauthorized test message attempt user_id=%s", user_id)
            return

        logger.info("Test message requested chat_id=%s user_id=%s", chat_id, user_id)
        demo_item = ItemCreate(
            item_name='My Item',
            item_amount=1,
            item_type='spare part',
            item_price=0.01,
            availability=True,
        )

        try:
            repository = ItemRepository(session)
            item = await repository.create_item(demo_item, chat_id, created_by_user_id=user_id)

            text = (
                f'Request is placed for processing:\n'
                f'Item name: {item.item_name}\n'
                f'Amount of items: {item.item_amount}\n'
                f'Item type: {item.item_type}\n'
                f'Item price: {item.item_price}\n'
                f'Availability: {item.availability}\n'
            )
            await msg.reply_text(text)
            logger.info("Test message sent chat_id=%s", chat_id)
            await msg.reply_text(
                'What would you like to do next?',
                reply_markup=self._back_to_menu_keyboard(),
            )
        except Exception as e:
            logger.error("Error sending test message: %s", type(e).__name__, exc_info=True)
            await msg.reply_text("Failed to process the request. Please try again later.")

    async def handle_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle admin command (admin only)."""
        clear_flow_state(context)
        msg = update.effective_message
        if not msg:
            return
        user_id = update.effective_user.id if update.effective_user else None
        session = context.bot_data.get("current_db_session") if context.bot_data else None
        role = await get_user_role(user_id, session, self.settings)
        if not is_admin_role(role):
            await msg.reply_text("You are not authorized to use this command.")
            logger.warning("Unauthorized admin menu attempt user_id=%s", user_id)
            return

        chat_id = update.effective_chat.id if update.effective_chat else None
        logger.info("Admin menu shown chat_id=%s user_id=%s", chat_id, user_id)
        await msg.reply_text(
            'Admin. Manage users or go back.',
            reply_markup=self._admin_menu_keyboard(),
        )

    async def _require_admin_and_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Return (session, chat_id, msg) if caller is admin and session exists; else None and reply sent."""
        msg = update.effective_message
        if not msg:
            return None, None, None
        user_id = update.effective_user.id if update.effective_user else None
        session = context.bot_data.get("current_db_session") if context.bot_data else None
        role = await get_user_role(user_id, session, self.settings)
        if not is_admin_role(role):
            await msg.reply_text("You are not authorized to use this command.")
            return None, None, None
        if session is None:
            await msg.reply_text("Database session not available. Please try again.")
            return None, None, None
        chat_id = update.effective_chat.id if update.effective_chat else None
        return session, chat_id, msg

    async def list_users(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """List all users (admin only)."""
        session, chat_id, msg = await self._require_admin_and_session(update, context)
        if session is None or msg is None or chat_id is None:
            return
        try:
            user_repo = UserRepository(session)
            users = await user_repo.list_users(limit=100)
            if not users:
                await msg.reply_text("No users in the database.")
            else:
                lines = []
                for u in users:
                    role_name = u.role.name if u.role else "?"
                    lines.append(f"id={u.id} telegram_id={u.telegram_user_id} role={role_name}")
                await msg.reply_text("Users:\n" + "\n".join(lines))
            await msg.reply_text("What next?", reply_markup=self._admin_menu_keyboard())
        except Exception as e:
            logger.error("Error listing users: %s", type(e).__name__, exc_info=True)
            await msg.reply_text("An error occurred. Please try again.")
            await msg.reply_text("What next?", reply_markup=self._admin_menu_keyboard())

    async def start_add_user(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Add user flow: ask for Telegram ID (admin only)."""
        _, _, msg = await self._require_admin_and_session(update, context)
        if msg is None:
            return
        clear_flow_state(context)
        context.user_data["state"] = "waiting_for_manage_add_user_id"
        await self.bot.send_message(
            chat_id,
            "Send the Telegram user ID (numeric). Or /cancel to cancel.",
            reply_markup=ForceReply(selective=True),
        )

    async def process_manage_add_user(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Process Telegram ID for Add user, then ask for role."""
        state = context.user_data.get("state")
        if state != "waiting_for_manage_add_user_id":
            return
        msg = update.effective_message
        if not msg or not update.message or not update.message.text or session is None:
            return
        raw = update.message.text.strip()
        if not raw or not raw.lstrip("-").isdigit():
            await msg.reply_text("Please send a numeric Telegram user ID. Or /cancel to cancel.")
            return
        tid = int(raw)
        context.user_data["manage_add_telegram_id"] = tid
        context.user_data["state"] = "waiting_for_manage_add_user_role"
        await msg.reply_text("Choose role:", reply_markup=self._manage_role_keyboard())

    async def apply_manage_add_user_role(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
        role_name: str,
    ) -> None:
        """Create user with stored Telegram ID and chosen role (admin only)."""
        if session is None:
            await self.bot.send_message(chat_id, "Database session not available. Please try again.")
            return
        tid = context.user_data.get("manage_add_telegram_id")
        if tid is None:
            await self.bot.send_message(chat_id, "Session expired. Start over from Admin menu.")
            clear_flow_state(context)
            return
        try:
            user_repo = UserRepository(session)
            existing = await user_repo.get_by_telegram_id(tid)
            if existing:
                await self.bot.send_message(chat_id, f"User with Telegram ID {tid} already exists.")
                clear_flow_state(context)
                await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())
                return
            await user_repo.create_user(tid, role_name)
            clear_flow_state(context)
            await self.bot.send_message(chat_id, f"User created: telegram_id={tid}, role={role_name}.")
            await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())
        except ValueError as e:
            await self.bot.send_message(chat_id, str(e))
            clear_flow_state(context)
            await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())
        except Exception as e:
            logger.error("Error creating user: %s", type(e).__name__, exc_info=True)
            await self.bot.send_message(chat_id, "An error occurred. Please try again.")
            clear_flow_state(context)
            await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())

    async def start_set_role(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Set role flow: ask for Telegram ID (admin only)."""
        _, _, msg = await self._require_admin_and_session(update, context)
        if msg is None:
            return
        clear_flow_state(context)
        context.user_data["state"] = "waiting_for_manage_set_role_id"
        await self.bot.send_message(
            chat_id,
            "Send the Telegram user ID (numeric). Or /cancel to cancel.",
            reply_markup=ForceReply(selective=True),
        )

    async def process_manage_set_role(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Process Telegram ID for Set role, then ask for role."""
        state = context.user_data.get("state")
        if state != "waiting_for_manage_set_role_id":
            return
        msg = update.effective_message
        if not msg or not update.message or not update.message.text or session is None:
            return
        raw = update.message.text.strip()
        if not raw or not raw.lstrip("-").isdigit():
            await msg.reply_text("Please send a numeric Telegram user ID. Or /cancel to cancel.")
            return
        tid = int(raw)
        context.user_data["manage_set_role_telegram_id"] = tid
        context.user_data["state"] = "waiting_for_manage_set_role_choice"
        await msg.reply_text("Choose new role:", reply_markup=self._manage_set_role_choice_keyboard())

    async def apply_manage_set_role_choice(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
        role_name: str,
    ) -> None:
        """Set role for stored Telegram ID (admin only)."""
        if session is None:
            await self.bot.send_message(chat_id, "Database session not available. Please try again.")
            return
        tid = context.user_data.get("manage_set_role_telegram_id")
        if tid is None:
            await self.bot.send_message(chat_id, "Session expired. Start over from Admin menu.")
            clear_flow_state(context)
            return
        try:
            user_repo = UserRepository(session)
            user = await user_repo.set_role(tid, role_name)
            clear_flow_state(context)
            if user:
                await self.bot.send_message(chat_id, f"Role set: telegram_id={tid} -> {role_name}.")
            else:
                await self.bot.send_message(chat_id, f"User with Telegram ID {tid} not found.")
            await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())
        except ValueError as e:
            await self.bot.send_message(chat_id, str(e))
            clear_flow_state(context)
            await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())
        except Exception as e:
            logger.error("Error setting role: %s", type(e).__name__, exc_info=True)
            await self.bot.send_message(chat_id, "An error occurred. Please try again.")
            clear_flow_state(context)
            await self.bot.send_message(chat_id, "What next?", reply_markup=self._admin_menu_keyboard())

    async def start_remove_user(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
        chat_id: int,
    ) -> None:
        """Start Remove user flow: ask for Telegram ID (admin only)."""
        _, _, msg = await self._require_admin_and_session(update, context)
        if msg is None:
            return
        clear_flow_state(context)
        context.user_data["state"] = "waiting_for_manage_remove_user_id"
        await self.bot.send_message(
            chat_id,
            "Send the Telegram user ID (numeric) to remove. Or /cancel to cancel.",
            reply_markup=ForceReply(selective=True),
        )

    async def process_manage_remove_user(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Process Telegram ID and delete user (admin only)."""
        state = context.user_data.get("state")
        if state != "waiting_for_manage_remove_user_id":
            return
        msg = update.effective_message
        if not msg or not update.message or not update.message.text or session is None:
            return
        raw = update.message.text.strip()
        if not raw or not raw.lstrip("-").isdigit():
            await msg.reply_text("Please send a numeric Telegram user ID. Or /cancel to cancel.")
            return
        tid = int(raw)
        clear_flow_state(context)
        try:
            user_repo = UserRepository(session)
            deleted = await user_repo.delete_user(tid)
            if deleted:
                await msg.reply_text(f"User with Telegram ID {tid} removed.")
            else:
                await msg.reply_text(f"User with Telegram ID {tid} not found.")
            await msg.reply_text("What next?", reply_markup=self._admin_menu_keyboard())
        except Exception as e:
            logger.error("Error removing user: %s", type(e).__name__, exc_info=True)
            await msg.reply_text("An error occurred. Please try again.")
            await msg.reply_text("What next?", reply_markup=self._admin_menu_keyboard())
    
    async def stop_bot(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Stop bot (admin only)."""
        msg = update.effective_message
        if not msg:
            return
        user_id = update.effective_user.id if update.effective_user else None
        session = context.bot_data.get("current_db_session") if context.bot_data else None
        role = await get_user_role(user_id, session, self.settings)
        if not is_admin_role(role):
            await msg.reply_text("You are not authorized to use this command.")
            logger.warning("Unauthorized stop attempt user_id=%s", user_id)
            return

        logger.info("Stop command from admin user_id=%s", user_id)
        await msg.reply_text(
            "Stop requested. In this setup the bot keeps running; your request has been logged."
        )
        logger.info("Bot stop requested")

    async def cancel_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Cancel any ongoing flow and reply."""
        clear_flow_state(context)
        msg = update.effective_message
        if msg:
            await msg.reply_text("Cancelled. Use /menu or the buttons below to choose an action.")

