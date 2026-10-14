from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.repositories.product_repository import (
    ProductRepository
)


class StockBalanceService:
    """Read-only service for current product stock balances."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductRepository(db)

    def list_stock_balances(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        stock_status: str | None = None,
        category_id: int | None = None,
        location_id: int | None = None,
        search: str | None = None,
        min_quantity: Decimal | None = None,
        max_quantity: Decimal | None = None,
        sort_by: str = "id"
    ) -> list[Product]:
        """Return current stock balances using repository filters."""
        return self.products.get_stock_balances(
            offset=offset,
            limit=limit,
            stock_status=stock_status,
            category_id=category_id,
            location_id=location_id,
            search=search,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            sort_by=sort_by
        )
