"""FastAPI dependencies."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session."""
    async with get_db_session() as session:
        yield session

