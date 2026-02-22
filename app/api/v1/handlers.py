"""Telegram bot handlers."""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from app.services.bot_service import BotService
from app.core.validators import check_working_hours

logger = logging.getLogger(__name__)


def register_handlers(application: Application, bot_service: BotService) -> None:
    """Register all bot handlers."""
    
    # Command handlers
    application.add_handler(CommandHandler("start", bot_service.send_welcome))
    application.add_handler(CommandHandler("menu", bot_service.send_menu))
    application.add_handler(CommandHandler("stop", bot_service.stop_bot))
    
    # Text message handlers
    async def handle_add(u, c):
        db = c.bot_data.get('current_db_session')
        await bot_service.handle_add_item(u, c, db)
    
    async def handle_get(u, c):
        db = c.bot_data.get('current_db_session')
        await bot_service.get_items(u, c, db)
    
    async def handle_test_message(u, c):
        db = c.bot_data.get('current_db_session')
        await bot_service.send_test_message(u, c, db)
    
    async def handle_availability(u, c):
        db = c.bot_data.get('current_db_session')
        await bot_service.update_availability_status(u, c, db)
    
    application.add_handler(
        MessageHandler(
            filters.Regex("^[Aa]dd$") | filters.Regex("^Add$"),
            handle_add,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex("^[Gg]et$") | filters.Regex("^Get$"),
            handle_get,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex("^[Aa]dmin$") | filters.Regex("^Admin$"),
            bot_service.handle_admin,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex("^Send test message$"),
            handle_test_message,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex("^Change availability status$"),
            handle_availability,
        )
    )
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Handle multi-step input (state-based)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_message,
        )
    )
    
    logger.info("Handlers registered")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries."""
    query = update.callback_query
    if query is None:
        return

    # Log callback action only (callback_data is fixed set: Get, Add, Admin, etc.)
    logger.info("Callback query update_id=%s data=%s", update.update_id, query.data)
    await query.answer()
    bot_service = context.bot_data.get('bot_service')
    if bot_service is None:
        logger.error("Bot service not found in context")
        return

    db_session = context.bot_data.get('current_db_session')

    if query.data == 'Add':
        await bot_service.handle_add_item(update, context, db_session)
    elif query.data == 'Get':
        await bot_service.get_items(update, context, db_session)
    elif query.data == 'Admin':
        await bot_service.handle_admin(update, context)
    elif query.data == 'Send test message':
        await bot_service.send_test_message(update, context, db_session)
    elif query.data == 'availability_status':
        await bot_service.update_availability_status(update, context, db_session)
    elif query.data == 'stop_bot':
        await bot_service.stop_bot(update, context)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages (for multi-step input)."""
    if update.message is None:
        return

    state = context.user_data.get('state')
    bot_service = context.bot_data.get('bot_service')
    db_session = context.bot_data.get('current_db_session')

    if state and bot_service:
        # Handle multi-step input (do not log message text)
        logger.debug("Text message in state flow update_id=%s state=%s", update.update_id, state)
        if state.startswith('waiting_for'):
            if 'item' in state:
                await bot_service.process_item_input(update, context, db_session)
            elif 'availability' in state:
                await bot_service.process_availability_update(update, context, db_session)

