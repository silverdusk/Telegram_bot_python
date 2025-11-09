"""Item schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ItemBase(BaseModel):
    """Base item schema."""
    item_name: str = Field(..., min_length=1, max_length=255, description="Item name")
    item_amount: int = Field(..., gt=0, description="Item amount")
    item_type: str = Field(..., description="Item type")
    item_price: Optional[float] = Field(None, ge=0, description="Item price")
    availability: bool = Field(default=False, description="Item availability")
    
    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str, info) -> str:
        """Validate item type against allowed types."""
        from app.core.config import get_settings
        settings = get_settings()
        if v.lower() not in [t.lower() for t in settings.allowed_types]:
            allowed = " or ".join(settings.allowed_types)
            raise ValueError(f"Item type must be one of: {allowed}")
        return v.lower()


class ItemCreate(ItemBase):
    """Schema for creating an item."""
    pass


class ItemResponse(ItemBase):
    """Schema for item response."""
    id: int
    chat_id: int
    timestamp: datetime
    
    model_config = {"from_attributes": True}


class ItemUpdate(BaseModel):
    """Schema for updating an item."""
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    item_amount: Optional[int] = Field(None, gt=0)
    item_type: Optional[str] = None
    item_price: Optional[float] = Field(None, ge=0)
    availability: Optional[bool] = None

