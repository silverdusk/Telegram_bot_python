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

logger = logging.getLogger(__name__)


def register_handlers(application: Application, bot_service: BotService) -> None:
    """Register all bot handlers."""
    
    # Command handlers
    application.add_handler(CommandHandler("start", bot_service.send_welcome))
    application.add_handler(CommandHandler("menu", bot_service.send_menu))
    application.add_handler(CommandHandler("cancel", bot_service.cancel_flow))
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

    async def handle_remove(u, c):
        db = c.bot_data.get('current_db_session')
        await bot_service.handle_remove_item(u, c, db)

    async def handle_update(u, c):
        db = c.bot_data.get('current_db_session')
        await bot_service.handle_update_item(u, c, db)

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
    application.add_handler(
        MessageHandler(
            filters.Regex("^Remove item$"),
            handle_remove,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Regex("^Update item$"),
            handle_update,
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
    chat_id = query.message.chat_id if query.message else None

    # Flow callbacks: fixed-option choices in multi-step flows
    _expired_msg = "This action has expired. Please start over with Add or Change availability status."
    if chat_id is not None and query.data.startswith('item_type_'):
        state = context.user_data.get('state')
        if state == 'waiting_for_item_type':
            item_type = query.data.replace('item_type_', '', 1)
            await bot_service.advance_after_item_type(context, db_session, chat_id, item_type)
        else:
            await bot_service.bot.send_message(chat_id, _expired_msg)
        return
    if chat_id is not None and query.data in ('item_availability_yes', 'item_availability_no'):
        state = context.user_data.get('state')
        if state == 'waiting_for_availability':
            context.user_data.setdefault('item_data', {})['availability'] = query.data == 'item_availability_yes'
            uid = query.from_user.id if query.from_user else None
            await bot_service._finish_add_item(context, db_session, chat_id, user_id=uid)
        else:
            await bot_service.bot.send_message(chat_id, _expired_msg)
        return
    if chat_id is not None and query.data in ('avail_status_yes', 'avail_status_no'):
        state = context.user_data.get('state')
        if state == 'waiting_for_availability_status':
            uid = query.from_user.id if query.from_user else None
            await bot_service.apply_availability_status_choice(
                context, db_session, chat_id, query.data == 'avail_status_yes', user_id=uid
            )
        else:
            await bot_service.bot.send_message(chat_id, _expired_msg)
        return
    if chat_id is not None and query.data == 'add_another':
        await bot_service.start_add_item_flow(context, db_session, chat_id)
        return
    if chat_id is not None and query.data == 'update_another_item':
        await bot_service.start_update_item_flow(context, db_session, chat_id)
        return
    if chat_id is not None and query.data == 'remove_another_item':
        await bot_service.start_remove_item_flow(context, db_session, chat_id)
        return
    if chat_id is not None and query.data == 'change_availability_again':
        await bot_service.start_availability_flow(context, db_session, chat_id)
        return
    if chat_id is not None and query.data == 'show_menu':
        await bot_service.send_menu_to_chat(chat_id)
        return
    if chat_id is not None and query.data and query.data.startswith('update_field'):
        await bot_service.apply_update_field_choice(context, db_session, chat_id, query.data)
        return

    if query.data == 'Add':
        await bot_service.handle_add_item(update, context, db_session)
    elif query.data == 'Get':
        await bot_service.get_items(update, context, db_session)
    elif query.data == 'remove_item':
        await bot_service.handle_remove_item(update, context, db_session)
    elif query.data == 'update_item':
        await bot_service.handle_update_item(update, context, db_session)
    elif query.data == 'Admin':
        await bot_service.handle_admin(update, context)
    elif query.data == 'Send test message':
        await bot_service.send_test_message(update, context, db_session)
    elif query.data == 'availability_status':
        await bot_service.update_availability_status(update, context, db_session)
    elif query.data == 'stop_bot':
        await bot_service.stop_bot(update, context)
    elif chat_id is not None and query.data == 'mu_list':
        await bot_service.list_users(update, context, db_session)
    elif chat_id is not None and query.data == 'mu_add':
        await bot_service.start_add_user(update, context, db_session, chat_id)
    elif chat_id is not None and query.data == 'mu_set_role':
        await bot_service.start_set_role(update, context, db_session, chat_id)
    elif chat_id is not None and query.data == 'mu_remove':
        await bot_service.start_remove_user(update, context, db_session, chat_id)
    elif chat_id is not None and query.data == 'mu_add_role_admin':
        await bot_service.apply_manage_add_user_role(context, db_session, chat_id, 'admin')
    elif chat_id is not None and query.data == 'mu_add_role_user':
        await bot_service.apply_manage_add_user_role(context, db_session, chat_id, 'user')
    elif chat_id is not None and query.data == 'mu_set_role_admin':
        await bot_service.apply_manage_set_role_choice(context, db_session, chat_id, 'admin')
    elif chat_id is not None and query.data == 'mu_set_role_user':
        await bot_service.apply_manage_set_role_choice(context, db_session, chat_id, 'user')


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages (for multi-step input or unhandled text)."""
    if update.message is None:
        return

    state = context.user_data.get('state')
    bot_service = context.bot_data.get('bot_service')
    db_session = context.bot_data.get('current_db_session')

    if state and bot_service and state.startswith('waiting_for'):
        # Handle multistep input (do not log message text)
        logger.debug("Text message in state flow update_id=%s state=%s", update.update_id, state)
        if state in ('waiting_for_availability_item_name', 'waiting_for_availability_status'):
            await bot_service.process_availability_update(update, context, db_session)
        elif state == 'waiting_for_remove_item_name':
            await bot_service.process_remove_item(update, context, db_session)
        elif state == 'waiting_for_manage_add_user_id':
            await bot_service.process_manage_add_user(update, context, db_session)
        elif state == 'waiting_for_manage_set_role_id':
            await bot_service.process_manage_set_role(update, context, db_session)
        elif state == 'waiting_for_manage_remove_user_id':
            await bot_service.process_manage_remove_user(update, context, db_session)
        elif state and state.startswith('waiting_for_update'):
            await bot_service.process_update_item(update, context, db_session)
        else:
            await bot_service.process_item_input(update, context, db_session)
    else:
        # Unhandled text: no active flow or unknown state
        await update.message.reply_text(
            "I didn't understand. Use /menu or the buttons below to choose an action."
        )

