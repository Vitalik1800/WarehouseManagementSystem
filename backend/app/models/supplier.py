from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    contact_person: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="supplier"
    )
