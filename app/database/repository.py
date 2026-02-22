"""Database repository for items."""
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload
from database.models import Item, User, Role
from app.schemas.item import ItemCreate, ItemUpdate

logger = logging.getLogger(__name__)


class ItemRepository:
    """Repository for item database operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    async def create_item(
        self,
        item_data: ItemCreate,
        chat_id: int,
        created_by_user_id: Optional[int] = None,
    ) -> Item:
        """Create a new item in the database."""
        try:
            item = Item(
                item_name=item_data.item_name,
                item_amount=item_data.item_amount,
                item_type=item_data.item_type,
                item_price=item_data.item_price,
                availability=item_data.availability,
                chat_id=chat_id,
                timestamp=datetime.utcnow(),
                created_by_user_id=created_by_user_id,
            )
            self.session.add(item)
            await self.session.flush()
            await self.session.refresh(item)
            logger.info(f"Item created: {item.id}")
            return item
        except Exception as e:
            logger.error(f"Error creating item: {e}")
            await self.session.rollback()
            raise

    async def get_item_by_id(self, item_id: int) -> Optional[Item]:
        """Get item by ID."""
        try:
            result = await self.session.execute(
                select(Item).where(Item.id == item_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Error getting item %s: %s", item_id, e)
            raise

    async def get_items(
        self,
        item_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        chat_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Item]:
        """Get items with optional filters. created_by_user_id restricts to that creator (None = all)."""
        try:
            query = select(Item)
            
            if item_name:
                query = query.where(Item.item_name.ilike(f"%{item_name}%"))
            
            if start_date and end_date:
                query = query.where(
                    and_(
                        Item.timestamp >= start_date,
                        Item.timestamp <= end_date,
                    )
                )
            
            if chat_id:
                query = query.where(Item.chat_id == chat_id)
            
            if created_by_user_id is not None:
                query = query.where(Item.created_by_user_id == created_by_user_id)
            
            query = query.limit(limit).order_by(Item.timestamp.desc())
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting items: {e}")
            raise
    
    async def update_availability(
        self,
        item_name: str,
        availability: bool,
        chat_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
    ) -> bool:
        """Update item availability by name. Optional chat_id and created_by_user_id restrict scope."""
        try:
            stmt = update(Item).where(Item.item_name.ilike(item_name)).values(availability=availability)
            if chat_id is not None:
                stmt = stmt.where(Item.chat_id == chat_id)
            if created_by_user_id is not None:
                stmt = stmt.where(Item.created_by_user_id == created_by_user_id)
            result = await self.session.execute(stmt)
            await self.session.flush()
            logger.info("Updated availability for %s: %s", item_name, availability)
            return result.rowcount > 0
        except Exception as e:
            logger.error("Error updating availability: %s", e)
            await self.session.rollback()
            raise

    async def delete_by_name_and_chat(
        self,
        item_name: str,
        chat_id: int,
        created_by_user_id: Optional[int] = None,
    ) -> int:
        """Delete items matching item_name and chat_id. If created_by_user_id set, only that creator's; else all (admin)."""
        try:
            stmt = delete(Item).where(Item.chat_id == chat_id).where(Item.item_name.ilike(item_name))
            if created_by_user_id is not None:
                stmt = stmt.where(Item.created_by_user_id == created_by_user_id)
            result = await self.session.execute(stmt)
            await self.session.flush()
            logger.info("Deleted %s item(s) for chat_id=%s name=%s", result.rowcount, chat_id, item_name)
            return result.rowcount or 0
        except Exception as e:
            logger.error("Error deleting item: %s", e)
            await self.session.rollback()
            raise

    async def update_item(
        self,
        item_id: int,
        item_data: ItemUpdate,
    ) -> Optional[Item]:
        """Update an item by ID. Returns updated item or None if not found."""
        try:
            item = await self.get_item_by_id(item_id)
            if not item:
                return None
            update_data = item_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(item, key, value)
            await self.session.flush()
            await self.session.refresh(item)
            logger.info("Item updated id=%s", item_id)
            return item
        except Exception as e:
            logger.error("Error updating item %s: %s", item_id, e)
            await self.session.rollback()
            raise


class UserRepository:
    """Repository for user and role operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_user_id: int):
        """Get user by Telegram user ID."""
        try:
            result = await self.session.execute(
                select(User).where(User.telegram_user_id == telegram_user_id).options(selectinload(User.role))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Error getting user by telegram_id %s: %s", telegram_user_id, e)
            raise

    async def list_users(self, limit: int = 100) -> List[User]:
        """List all users with role loaded."""
        try:
            result = await self.session.execute(
                select(User).options(selectinload(User.role)).limit(limit).order_by(User.id)
            )
            return list(result.scalars().unique().all())
        except Exception as e:
            logger.error("Error listing users: %s", e)
            raise

    async def create_user(self, telegram_user_id: int, role_name: str) -> User:
        """Create user with given role (role must exist)."""
        try:
            role_result = await self.session.execute(select(Role).where(Role.name == role_name))
            role = role_result.scalar_one_or_none()
            if not role:
                raise ValueError(f"Role {role_name} not found")
            user = User(telegram_user_id=telegram_user_id, role_id=role.id)
            self.session.add(user)
            await self.session.flush()
            await self.session.refresh(user)
            logger.info("User created telegram_user_id=%s role=%s", telegram_user_id, role_name)
            return user
        except Exception as e:
            logger.error("Error creating user: %s", e)
            await self.session.rollback()
            raise

    async def set_role(self, telegram_user_id: int, role_name: str) -> Optional[User]:
        """Set user role by name. Returns updated user or None if user not found."""
        try:
            user = await self.get_by_telegram_id(telegram_user_id)
            if not user:
                return None
            role_result = await self.session.execute(select(Role).where(Role.name == role_name))
            role = role_result.scalar_one_or_none()
            if not role:
                raise ValueError(f"Role {role_name} not found")
            user.role_id = role.id
            await self.session.flush()
            await self.session.refresh(user)
            logger.info("User role set telegram_user_id=%s role=%s", telegram_user_id, role_name)
            return user
        except Exception as e:
            logger.error("Error setting role: %s", e)
            await self.session.rollback()
            raise

    async def delete_user(self, telegram_user_id: int) -> bool:
        """Remove user by Telegram ID. Returns True if deleted."""
        try:
            result = await self.session.execute(delete(User).where(User.telegram_user_id == telegram_user_id))
            await self.session.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error("Error deleting user: %s", e)
            await self.session.rollback()
            raise
