"""FastAPI application main entry point."""
import logging
import logging.config
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.database.session import init_db, close_db, create_tables, seed_roles, ensure_indexes
from app.api.v1 import webhook
from app.api.v1.webhook import get_bot_application
from app.api.v1.admin import admin_router, AdminAuthMiddleware

# Configure logging: use logging.ini if present, else basicConfig (e.g. in Docker)
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOG_INI = os.path.join(_ROOT_DIR, "logging.ini")
if os.path.isfile(_LOG_INI):
    logging.config.fileConfig(_LOG_INI)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting application...")
    try:
        settings = get_settings()
        # Initialize database
        init_db()
        if settings.create_tables_on_startup:
            await create_tables()
            await seed_roles()
            await ensure_indexes()
            logger.info("Database tables created")
        else:
            await ensure_indexes()
        logger.info("Database initialized")

        # Initialize Telegram bot application (webhook mode)
        await get_bot_application()
        logger.info("Telegram bot application ready")
    except Exception:
        logger.critical("Startup failed", exc_info=True)
        raise

    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()

    from app.api.v1 import webhook as webhook_module
    if webhook_module.bot_application is not None:
        await webhook_module.bot_application.shutdown()

    logger.info("Application shut down")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="Telegram Bot API with FastAPI",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    
    # CORS middleware (use CORS_ORIGINS env in production to restrict)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AdminAuthMiddleware)

    # Static files
    _static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    # Include routers
    app.include_router(webhook.router)
    app.include_router(admin_router)
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Telegram Bot API",
            "status": "running",
        }
    
    return app


# Create application instance
app = create_application()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )

