"""Telegram bot service for handling bot logic."""
import logging
from typing import Optional
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from telegram.ext import ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repository import ItemRepository
from app.schemas.item import ItemCreate
from app.core.validators import (
    validate_text_input,
    is_int,
    is_float,
    check_working_hours,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def clear_flow_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear any ongoing flow state so user starts from a clean slate."""
    for key in ('state', 'item_data', 'availability_item_name'):
        context.user_data.pop(key, None)


class BotService:
    """Service for handling Telegram bot operations."""

    def __init__(self, bot: Bot):
        """Initialize bot service."""
        self.bot = bot
        self.settings = get_settings()

    async def send_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message with keyboard."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        logger.info("Command /start chat_id=%s", chat_id)
        keyboard = [
            [KeyboardButton('Get'), KeyboardButton('Add')],
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
        keyboard = [
            [
                InlineKeyboardButton('Get', callback_data='Get'),
                InlineKeyboardButton('Add', callback_data='Add'),
            ],
            [
                InlineKeyboardButton('Admin', callback_data='Admin'),
                InlineKeyboardButton('Change availability status', callback_data='availability_status'),
            ],
            [
                InlineKeyboardButton('Send test message', callback_data='Send test message'),
                InlineKeyboardButton('Stop', callback_data='stop_bot'),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
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
            if not validate_text_input(update.message.text):
                await update.message.reply_text(
                    'Invalid name. Please use letters and numbers.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None

            item_data['item_name'] = update.message.text.upper()
            context.user_data['state'] = 'waiting_for_item_amount'
            await update.message.reply_text(
                'Please provide amount of items.\nOr /cancel to cancel.',
                reply_markup=ForceReply(selective=True),
            )
            return None

        elif state == 'waiting_for_item_amount':
            if not is_int(update.message.text):
                await update.message.reply_text(
                    'Invalid amount. Please enter a whole number.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None

            item_data['item_amount'] = int(update.message.text)
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
            if not is_float(update.message.text):
                await update.message.reply_text(
                    'Invalid price. Please enter a number.\nOr /cancel to cancel.',
                    reply_markup=ForceReply(selective=True),
                )
                return None

            item_data['item_price'] = float(update.message.text)
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
        return await self._finish_add_item(context, session, chat_id)

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
            item = await repository.create_item(item_create, chat_id)
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
            return item_create
        except Exception as e:
            logger.error("Error creating item: %s", type(e).__name__, exc_info=True)
            await self.bot.send_message(chat_id, "Failed to process the request. Please try again later.")
            return None
    
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
        except Exception as e:
            logger.error("Error getting items: %s", type(e).__name__, exc_info=True)
            await msg.reply_text("An error occurred. Please try again later.")
    
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
            item_name = update.message.text.upper()
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
                repository = ItemRepository(session)
                updated = await repository.update_availability(item_name, availability)
                
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
            repository = ItemRepository(session)
            updated = await repository.update_availability(item_name, availability)
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
        except Exception as e:
            logger.error("Error updating availability: %s", type(e).__name__, exc_info=True)
            await self.bot.send_message(chat_id, "An error occurred. Please try again later.")
    
    async def send_test_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession | None,
    ) -> None:
        """Send test/demo message."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        if session is None:
            await msg.reply_text("Database session not available. Please try again.")
            return

        logger.info("Test message requested chat_id=%s", chat_id)
        demo_item = ItemCreate(
            item_name='My Item',
            item_amount=1,
            item_type='spare part',
            item_price=0.01,
            availability=True,
        )

        try:
            repository = ItemRepository(session)
            item = await repository.create_item(demo_item, chat_id)

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
        except Exception as e:
            logger.error("Error sending test message: %s", type(e).__name__, exc_info=True)
            await msg.reply_text("Failed to process the request. Please try again later.")

    async def handle_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle admin command (placeholder)."""
        clear_flow_state(context)
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if msg:
            logger.info("Admin menu shown chat_id=%s", chat_id)
            await msg.reply_photo(
                photo='https://cdn-icons-png.flaticon.com/512/249/249389.png',
                caption="We're working on it!",
                protect_content=True,
            )
    
    async def stop_bot(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Stop bot (authorized users only)."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        msg = update.effective_message
        if not msg:
            return
        if chat_id not in self.settings.authorized_ids:
            await msg.reply_text("You are not authorized to use this command.")
            logger.warning("Unauthorized stop attempt chat_id=%s", chat_id)
            return

        logger.info("Stop command from authorized user chat_id=%s", chat_id)
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

