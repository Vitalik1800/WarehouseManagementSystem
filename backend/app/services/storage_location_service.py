from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.storage_location import StorageLocation
from backend.app.repositories.warehouse_repository import WarehouseRepository
from backend.app.repositories.storage_location_repository import (
    StorageLocationRepository
)
from backend.app.schemas.storage_locations import (
    StorageLocationCreate,
    StorageLocationUpdate
)

from backend.app.core.database_errors import (
    is_duplicate_entry,
    is_row_referenced
)


class StorageLocationNotFoundError(Exception):
    pass


class StorageLocationAlreadyExistsError(Exception):
    pass


class StorageLocationInUseError(Exception):
    pass


class StorageLocationWarehouseNotFoundError(Exception):
    pass


class StorageLocationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.locations = StorageLocationRepository(db)
        self.warehouses = WarehouseRepository(db)

    def get_location(
            self,
            location_id: int
    ) -> StorageLocation:
        location = self.locations.get_by_id(location_id)

        if location is None:
            raise StorageLocationNotFoundError(
                "Місце зберігання не знайдено"
            )

        return location

    def list_locations(
            self,
            *,
            offset: int = 0,
            limit: int = 50
    ) -> list[StorageLocation]:
        return self.locations.get_all(
            offset=offset,
            limit=limit
        )

    def create_location(
            self,
            data: StorageLocationCreate
    ) -> StorageLocation:
        if self.locations.get_by_name(data.name) is not None:
            raise StorageLocationAlreadyExistsError(
                "Місце зберігання з такою назвою вже існує"
            )

        if data.warehouse_id is None:
            warehouse = self.warehouses.get_by_code('MAIN')
        else:
            warehouse = self.warehouses.get_by_id(data.warehouse_id)

        if warehouse is None:
            raise StorageLocationWarehouseNotFoundError(
                'Warehouse not found'
            )

        try:
            values = data.model_dump(exclude={'warehouse_id'})
            location = self.locations.create(
                **values,
                warehouse_id=warehouse.id
            )

            self.db.commit()
            self.db.refresh(location)

            return location

        except IntegrityError as exc:
            self.db.rollback()

            if is_duplicate_entry(exc):
                raise StorageLocationAlreadyExistsError(
                    "Місце зберігання з такою назвою вже існує"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise

    def update_location(
            self,
            location_id: int,
            data: StorageLocationUpdate
    ) -> StorageLocation:
        location = self.get_location(location_id)

        changes = data.model_dump(exclude_unset=True)

        if not changes:
            return location

        if "name" in changes:
            existing = self.locations.get_by_name(
                changes["name"]
            )

            if existing is not None and existing.id != location_id:
                raise StorageLocationAlreadyExistsError(
                    "Місце зберігання з такою назвою вже існує"
                )

        try:
            for field, value in changes.items():
                setattr(location, field, value)

            self.db.commit()
            self.db.refresh(location)

            return location

        except IntegrityError as exc:
            self.db.rollback()

            if is_duplicate_entry(exc):
                raise StorageLocationAlreadyExistsError(
                    "Місце зберігання з такою назвою вже існує"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise

    def delete_location(
            self,
            location_id: int
    ) -> None:
        location = self.get_location(location_id)

        if self.locations.has_products(location_id):
            raise StorageLocationInUseError(
                "Неможливо видалити місце зберігання, "
                "оскільки до нього прив'язані товари"
            )

        try:
            self.locations.delete(location)
            self.db.commit()

        except IntegrityError as exc:
            self.db.rollback()

            if is_row_referenced(exc):
                raise StorageLocationInUseError(
                    "Неможливо видалити місце зберігання, "
                    "оскільки воно використовується"
                ) from exc

            raise

        except Exception:
            self.db.rollback()
            raise
