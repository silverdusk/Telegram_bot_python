"""Role and permission helpers. Resolve role from DB or fallback config."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import User, Role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.config import Settings

logger = logging.getLogger(__name__)


async def get_user_role(
    user_id: int | None,
    session: AsyncSession,
    settings: Settings,
) -> str | None:
    """
    Resolve role for Telegram user_id: 'admin', 'user', or None (unknown).
    Checks DB first; if user not in DB or DB error, uses fallback_admin_ids.
    """
    if user_id is None:
        return None
    try:
        result = await session.execute(
            select(User).where(User.telegram_user_id == user_id).options(selectinload(User.role))
        )
        user = result.scalar_one_or_none()
        if user and user.role:
            return user.role.name
    except Exception as e:
        logger.warning("Could not resolve role from DB for user_id=%s: %s", user_id, e)
    if user_id in settings.effective_fallback_admin_ids:
        return "admin"
    return "user"


def is_admin_role(role: str | None) -> bool:
    return role == "admin"


async def is_admin(
    user_id: int | None,
    session: AsyncSession,
    settings: Settings,
) -> bool:
    role = await get_user_role(user_id, session, settings)
    return is_admin_role(role)


def can_manage_item(
    created_by_user_id: int | None,
    current_user_id: int | None,
    role: str | None,
) -> bool:
    """
    True if current user can update/delete the item.
    Admin can manage any; user only if they created it (or item has no creator).
    """
    if current_user_id is None or role is None:
        return False
    if role == "admin":
        return True
    if role == "user":
        if created_by_user_id is None:
            return False
        return created_by_user_id == current_user_id
    return False
