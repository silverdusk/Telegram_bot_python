"""Webhook router for Telegram bot."""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes
from app.core.dependencies import get_db
from app.core.config import get_settings
from app.services.bot_service import BotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Global bot application instance
bot_application: Application | None = None
bot_service: BotService | None = None


async def get_bot_application() -> tuple[Application, BotService]:
    """Get or create bot application instance."""
    global bot_application, bot_service
    
    if bot_application is None:
        settings = get_settings()
        bot_application = Application.builder().token(settings.bot_token).build()
        bot = bot_application.bot
        bot_service = BotService(bot)
        
        # Store bot_service in bot_data for handlers to access
        bot_application.bot_data['bot_service'] = bot_service
        
        # Register handlers
        from app.api.v1.handlers import register_handlers
        register_handlers(bot_application, bot_service)

        # Initialize application:
        await bot_application.initialize()
        
        logger.info("Bot application initialized")
    
    return bot_application, bot_service


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle Telegram webhook updates.
    
    Args:
        request: FastAPI request object
        x_telegram_bot_api_secret_token: Secret token for webhook verification
        db: Database session
    
    Returns:
        Response dict
    """
    settings = get_settings()
    
    # Verify secret token if configured
    if settings.webhook_secret_token:
        if x_telegram_bot_api_secret_token != settings.webhook_secret_token:
            logger.warning("Invalid webhook secret token")
            raise HTTPException(status_code=403, detail="Invalid secret token")
    
    try:
        # Get update from request body
        update_data = await request.json()
        update = Update.de_json(update_data, None)
        
        if update is None:
            logger.warning("Received invalid update")
            return {"ok": False, "error": "Invalid update"}
        
        # Process update with bot application
        app, _ = await get_bot_application()
        
        # Process update (context is created automatically)
        # We need to pass db session through update callback data
        # Store in a temporary location that handlers can access
        app.bot_data['current_db_session'] = db
        
        # Process update
        await app.process_update(update)
        
        # Clean up
        app.bot_data.pop('current_db_session', None)
        
        logger.info(f"Processed update {update.update_id}")
        return {"ok": True}
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}

