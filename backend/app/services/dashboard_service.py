from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.category import Category
from backend.app.models.product import Product
from backend.app.models.storage_location import StorageLocation
from backend.app.models.supplier import Supplier
from backend.app.schemas.dashboard import DashboardSummaryResponse


class DashboardService:
    """Сервіс статистики головної панелі."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _count(self, model, *conditions) -> int:
        statement = select(func.count()).select_from(model)

        if conditions:
            statement = statement.where(*conditions)

        return int(self.db.scalar(statement) or 0)

    def get_summary(self) -> DashboardSummaryResponse:
        return DashboardSummaryResponse(
            total_products=self._count(Product),
            total_categories=self._count(Category),
            total_suppliers=self._count(Supplier),
            total_locations=self._count(StorageLocation),
            in_stock_products=self._count(
                Product,
                Product.quantity > 0,
            ),
            out_of_stock_products=self._count(
                Product,
                Product.quantity == 0,
            )
        )
