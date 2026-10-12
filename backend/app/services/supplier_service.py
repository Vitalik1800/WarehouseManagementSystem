from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.supplier import Supplier
from backend.app.repositories.supplier_repository import (
    SupplierRepository
)
from backend.app.schemas.suppliers import (
    SupplierCreate,
    SupplierUpdate
)

from backend.app.core.database_errors import is_row_referenced


class SupplierNotFoundError(Exception):
    pass


class SupplierInUseError(Exception):
    pass


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.suppliers = SupplierRepository(db)

    def get_supplier(self, supplier_id: int) -> Supplier:
        supplier = self.suppliers.get_by_id(supplier_id)

        if supplier is None:
            raise SupplierNotFoundError(
                "Постачальника не знайдено"
            )

        return supplier

    def list_suppliers(
        self,
        *,
        offset: int = 0,
        limit: int = 50
    ) -> list[Supplier]:
        return self.suppliers.get_all(
            offset=offset,
            limit=limit
        )

    def create_supplier(
        self,
        data: SupplierCreate
    ) -> Supplier:
        try:
            supplier = self.suppliers.create(
                **data.model_dump()
            )

            self.db.commit()
            self.db.refresh(supplier)

            return supplier

        except Exception:
            self.db.rollback()
            raise

    def update_supplier(
        self,
        supplier_id: int,
        data: SupplierUpdate
    ) -> Supplier:
        supplier = self.get_supplier(supplier_id)

        changes = data.model_dump(exclude_unset=True)

        if not changes:
            return supplier

        try:
            for field, value in changes.items():
                setattr(supplier, field, value)

            self.db.commit()
            self.db.refresh(supplier)

            return supplier

        except Exception:
            self.db.rollback()
            raise

    def delete_supplier(self, supplier_id: int) -> None:
        supplier = self.get_supplier(supplier_id)

        if self.suppliers.has_stock_movements(supplier_id):
            raise SupplierInUseError(
                "Неможливо видалити постачальника, "
                "оскільки він використовується "
                "в операціях руху товарів"
            )

        try:
            self.suppliers.delete(supplier)
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            if is_row_referenced(exc):
                raise SupplierInUseError(
                    "Неможливо видалити постачальника, "
                    "оскільки він використовується"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise
