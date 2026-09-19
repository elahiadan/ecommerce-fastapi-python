"""Category ORM model."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    products: Mapped[list["Product"]] = relationship(
        back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<Category {self.name} (id={self.id})>"