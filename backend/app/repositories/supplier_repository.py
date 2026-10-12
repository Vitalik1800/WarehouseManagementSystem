from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.app.models.stock_movement import StockMovement
from backend.app.models.supplier import Supplier


class SupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, supplier_id: int) -> Supplier | None:
        return self.db.get(Supplier, supplier_id)

    def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50
    ) -> list[Supplier]:
        if offset < 0:
            raise ValueError("Offset must not be negative")

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit must be between 1 and 100"
            )

        statement = (
            select(Supplier)
            .order_by(Supplier.id)
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    def create(
        self,
        *,
        name: str,
        contact_person: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None
    ) -> Supplier:
        supplier = Supplier(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address
        )

        self.db.add(supplier)
        self.db.flush()

        return supplier

    def has_stock_movements(self, supplier_id: int) -> bool:
        statement = select(
            exists().where(
                StockMovement.supplier_id == supplier_id
            )
        )

        return bool(self.db.scalar(statement))

    def delete(self, supplier: Supplier) -> None:
        self.db.delete(supplier)
