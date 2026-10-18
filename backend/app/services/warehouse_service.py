from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database_errors import is_duplicate_entry, is_row_referenced
from backend.app.repositories.warehouse_repository import WarehouseRepository
from backend.app.schemas.warehouses import WarehouseCreate, WarehouseUpdate


class WarehouseNotFoundError(Exception):
    pass


class WarehouseAlreadyExistsError(Exception):
    pass


class WarehouseInUseError(Exception):
    pass


class WarehouseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.warehouses = WarehouseRepository(db)

    def get_warehouse(self, warehouse_id: int):
        warehouse = self.warehouses.get_by_id(warehouse_id)
        if warehouse is None:
            raise WarehouseNotFoundError("Склад не знайдено")
        return warehouse

    def list_warehouses(self, *, offset: int = 0, limit: int = 50):
        return self.warehouses.get_all(offset=offset, limit=limit)

    def _ensure_unique(self, *, name=None, code=None, excluded_id=None):
        for value, getter in ((name, self.warehouses.get_by_name),
                              (code, self.warehouses.get_by_code)):
            if value is not None:
                existing = getter(value)
                if existing is not None and existing.id != excluded_id:
                    raise WarehouseAlreadyExistsError("Склад з такою назвою або кодом вже існує")

    def create_warehouse(self, data: WarehouseCreate):
        self._ensure_unique(name=data.name, code=data.code)
        try:
            warehouse = self.warehouses.create(**data.model_dump())
            self.db.commit()
            self.db.refresh(warehouse)
            return warehouse
        except IntegrityError as exc:
            self.db.rollback()
            if is_duplicate_entry(exc):
                raise WarehouseAlreadyExistsError("Склад з такою назвою або кодом вже існує") from exc
            raise
        except Exception:
            self.db.rollback()
            raise

    def update_warehouse(self, warehouse_id: int, data: WarehouseUpdate):
        warehouse = self.get_warehouse(warehouse_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return warehouse
        self._ensure_unique(name=changes.get("name"), code=changes.get("code"),
                            excluded_id=warehouse_id)
        try:
            for field, value in changes.items():
                setattr(warehouse, field, value)
            self.db.commit()
            self.db.refresh(warehouse)
            return warehouse
        except IntegrityError as exc:
            self.db.rollback()
            if is_duplicate_entry(exc):
                raise WarehouseAlreadyExistsError("Склад з такою назвою або кодом вже існує") from exc
            raise
        except Exception:
            self.db.rollback()
            raise

    def delete_warehouse(self, warehouse_id: int) -> None:
        warehouse = self.get_warehouse(warehouse_id)
        try:
            self.warehouses.delete(warehouse)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_row_referenced(exc):
                raise WarehouseInUseError("Склад використовується") from exc
            raise
        except Exception:
            self.db.rollback()
            raise
