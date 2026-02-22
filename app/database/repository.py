"""Database repository for items."""
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload
from database.models import Item
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
            logger.error(f"Error getting item {item_id}: {e}")
            raise
    
    async def get_items(
        self,
        item_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        chat_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Item]:
        """Get items with optional filters."""
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
    ) -> bool:
        """Update item availability by name."""
        try:
            result = await self.session.execute(
                update(Item)
                .where(Item.item_name.ilike(item_name))
                .values(availability=availability)
            )
            await self.session.flush()
            logger.info(f"Updated availability for {item_name}: {availability}")
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating availability: {e}")
            await self.session.rollback()
            raise

    async def delete_by_name_and_chat(self, item_name: str, chat_id: int) -> int:
        """Delete all items matching item_name (case-insensitive) for the given chat_id. Returns number of rows deleted."""
        try:
            result = await self.session.execute(
                delete(Item).where(Item.chat_id == chat_id).where(Item.item_name.ilike(item_name))
            )
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
        """Update an item."""
        try:
            item = await self.get_item_by_id(item_id)
            if not item:
                return None
            
            update_data = item_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(item, key, value)
            
            await self.session.flush()
            await self.session.refresh(item)
            logger.info(f"Item updated: {item_id}")
            return item
        except Exception as e:
            logger.error(f"Error updating item {item_id}: {e}")
            await self.session.rollback()
            raise

