from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name="quantity_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    sku: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pcs",
        server_default="pcs"
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0.000"),
        server_default="0.000"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    location_id: Mapped[int] = mapped_column(
        ForeignKey("storage_locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    category: Mapped["Category"] = relationship(
        back_populates="products"
    )

    location: Mapped["StorageLocation"] = relationship(
        back_populates="products"
    )

    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="product"
    )
