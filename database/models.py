"""SQLAlchemy models using 2.0 async patterns."""
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, DateTime, Boolean, Numeric, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Role(Base):
    """Role for user (admin, user)."""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"


class User(Base):
    """User linked to Telegram account; role from DB or fallback config."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    # Optional encrypted payload for future credentials/sensitive data
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    role: Mapped["Role"] = relationship("Role", back_populates="users")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_user_id={self.telegram_user_id}, role_id={self.role_id})>"


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
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<Item(id={self.id}, item_name={self.item_name}, item_amount={self.item_amount})>"
