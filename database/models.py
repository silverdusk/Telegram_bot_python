"""SQLAlchemy models using 2.0 async patterns."""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Item(Base):
    """Item model for organizer table."""
    __tablename__ = 'organizer_table'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(String(255), nullable=False)
    item_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    availability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Item(id={self.id}, item_name={self.item_name}, item_amount={self.item_amount})>"
