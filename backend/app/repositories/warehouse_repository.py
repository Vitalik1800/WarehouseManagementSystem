from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.warehouse import Warehouse


class WarehouseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, warehouse_id: int) -> Warehouse | None:
        return self.db.get(Warehouse, warehouse_id)

    def get_by_name(self, name: str) -> Warehouse | None:
        return self.db.scalar(select(Warehouse).where(Warehouse.name == name))

    def get_by_code(self, code: str) -> Warehouse | None:
        return self.db.scalar(select(Warehouse).where(Warehouse.code == code))

    def get_all(self, *, offset: int = 0, limit: int = 50) -> list[Warehouse]:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid pagination")
        stmt = select(Warehouse).order_by(Warehouse.id).offset(offset).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **values) -> Warehouse:
        warehouse = Warehouse(**values)
        self.db.add(warehouse)
        self.db.flush()
        return warehouse

    def delete(self, warehouse: Warehouse) -> None:
        self.db.delete(warehouse)
