from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.models.stock_movement import StockMovement


class StockMovementRepository:
    """Repository for warehouse stock movements."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(
        self,
        movement_id: int
    ) -> StockMovement | None:
        return self.db.get(StockMovement, movement_id)

    def get_product(
        self,
        product_id: int
    ) -> Product | None:
        return self.db.get(Product, product_id)

    def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        product_id: int | None = None,
        user_id: int | None = None,
        supplier_id: int | None = None,
        movement_type: str | None = None
    ) -> list[StockMovement]:
        if offset < 0:
            raise ValueError("Offset must not be negative")

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit must be between 1 and 100"
            )

        statement = select(StockMovement)

        if product_id is not None:
            statement = statement.where(
                StockMovement.product_id == product_id
            )

        if user_id is not None:
            statement = statement.where(
                StockMovement.user_id == user_id
            )

        if supplier_id is not None:
            statement = statement.where(
                StockMovement.supplier_id == supplier_id
            )

        if movement_type is not None:
            statement = statement.where(
                StockMovement.movement_type == movement_type
            )

        statement = (
            statement
            .order_by(
                StockMovement.created_at.desc(),
                StockMovement.id.desc()
            )
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.scalars(statement).all()
        )

    def create(
        self,
        *,
        product_id: int,
        user_id: int,
        movement_type: str,
        quantity: Decimal,
        supplier_id: int | None = None,
        note: str | None = None
    ) -> StockMovement:
        movement = StockMovement(
            product_id=product_id,
            user_id=user_id,
            supplier_id=supplier_id,
            movement_type=movement_type,
            quantity=quantity,
            note=note
        )

        self.db.add(movement)
        self.db.flush()

        return movement

    def increase_stock(
        self,
        product_id: int,
        quantity: Decimal
    ) -> bool:
        if quantity <= Decimal("0"):
            raise ValueError(
                "Quantity must be positive"
            )

        statement = (
            update(Product)
            .where(Product.id == product_id)
            .where(
                Product.quantity
                <= Decimal("99999999999.999") - quantity
            )
            .values(
                quantity=Product.quantity + quantity
            )
            .execution_options(
                synchronize_session="fetch"
            )
        )

        result = self.db.execute(statement)

        return result.rowcount == 1

    def decrease_stock(
        self,
        product_id: int,
        quantity: Decimal
    ) -> bool:
        if quantity <= Decimal("0"):
            raise ValueError(
                "Quantity must be positive"
            )

        statement = (
            update(Product)
            .where(Product.id == product_id)
            .where(Product.quantity >= quantity)
            .values(
                quantity=Product.quantity - quantity
            )
            .execution_options(
                synchronize_session="fetch"
            )
        )

        result = self.db.execute(statement)

        return result.rowcount == 1
