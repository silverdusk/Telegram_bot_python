"""Database session management."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import select, text
from app.core.config import get_settings
from database.models import Base, Role

logger = logging.getLogger(__name__)

# Global engine and session factory
engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """Initialize database connection."""
    global engine, async_session_maker
    
    settings = get_settings()
    engine = create_async_engine(
        settings.database.db_url,
        echo=settings.debug,
        future=True,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
    )
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    logger.info("Database connection initialized")


async def close_db() -> None:
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager."""
    if async_session_maker is None:
        init_db()
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all database tables."""
    if engine is None:
        init_db()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


# Index definitions (CREATE INDEX IF NOT EXISTS — safe to run on every startup)
_ORGANIZER_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_organizer_chat_timestamp
  ON organizer_table (chat_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_organizer_chat_name
  ON organizer_table (chat_id, item_name);
CREATE INDEX IF NOT EXISTS idx_organizer_created_by_user_id
  ON organizer_table (created_by_user_id)
  WHERE created_by_user_id IS NOT NULL;
"""


async def ensure_indexes() -> None:
    """Ensure performance indexes exist on organizer_table. Idempotent (IF NOT EXISTS)."""
    if engine is None:
        init_db()
    async with engine.begin() as conn:
        for stmt in _ORGANIZER_INDEXES_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    logger.info("Database indexes ensured")


async def seed_roles() -> None:
    """Ensure default roles (admin, user) exist. Call after create_tables."""
    if async_session_maker is None:
        init_db()
    async with async_session_maker() as session:
        try:
            result = await session.execute(select(Role))
            existing = {r.name for r in result.scalars().all()}
            if "admin" not in existing:
                session.add(Role(name="admin"))
            if "user" not in existing:
                session.add(Role(name="user"))
            await session.commit()
            logger.info("Roles seeded")
        except Exception as e:
            await session.rollback()
            logger.warning("Could not seed roles: %s", e)
            raise

