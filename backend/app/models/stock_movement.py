from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class StockMovement(Base):
    __tablename__ = "stock_movements"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive"
        ),
        CheckConstraint(
            "movement_type IN ('receipt', 'issue', 'writeoff')",
            name="movement_type_valid"
        )
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )

    movement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp()
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    product: Mapped["Product"] = relationship(
        back_populates="stock_movements"
    )

    user: Mapped["User"] = relationship(
        back_populates="stock_movements"
    )

    supplier: Mapped["Supplier | None"] = relationship(
        back_populates="stock_movements"
    )