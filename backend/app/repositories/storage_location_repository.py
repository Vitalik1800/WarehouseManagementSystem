from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.models.storage_location import StorageLocation


class StorageLocationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(
        self,
        location_id: int
    ) -> StorageLocation | None:
        return self.db.get(StorageLocation, location_id)

    def get_by_name(
        self,
        name: str
    ) -> StorageLocation | None:
        statement = select(StorageLocation).where(
            StorageLocation.name == name
        )

        return self.db.scalar(statement)

    def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50
    ) -> list[StorageLocation]:
        if offset < 0:
            raise ValueError("Offset must not be negative")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")

        statement = (
            select(StorageLocation)
            .order_by(StorageLocation.id)
            .offset(offset)
            .limit(limit)
        )

        return list(self.db.scalars(statement).all())

    def create(
        self,
        *,
        name: str,
        warehouse_id: int,
        description: str | None = None
    ) -> StorageLocation:
        location = StorageLocation(
            name=name,
            description=description,
            warehouse_id=warehouse_id
        )

        self.db.add(location)
        self.db.flush()

        return location

    def has_products(
        self,
        location_id: int
    ) -> bool:
        statement = select(
            exists().where(
                Product.location_id == location_id
            )
        )

        return bool(self.db.scalar(statement))

    def delete(
        self,
        location: StorageLocation
    ) -> None:
        self.db.delete(location)
