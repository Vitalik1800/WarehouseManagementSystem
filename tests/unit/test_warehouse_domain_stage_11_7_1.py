import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base
from backend.app.models.warehouse import Warehouse
from backend.app.models.storage_location import StorageLocation
from backend.app.schemas.warehouses import WarehouseCreate, WarehouseUpdate
from backend.app.services.warehouse_service import (
    WarehouseService, WarehouseAlreadyExistsError, WarehouseNotFoundError
)


@pytest.fixture
def warehouse_service():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Warehouse.__table__.create(engine)
    StorageLocation.__table__.create(engine)
    with Session(engine) as session:
        yield WarehouseService(session)
    engine.dispose()


def test_create_and_list(warehouse_service):
    created = warehouse_service.create_warehouse(WarehouseCreate(name=" Main ", code=" WH-1 "))
    assert created.id > 0
    assert created.name == "Main" and created.code == "WH-1"
    assert warehouse_service.list_warehouses()[0].id == created.id


def test_unique_name_and_code(warehouse_service):
    warehouse_service.create_warehouse(WarehouseCreate(name="Main", code="WH-1"))
    for name, code in (("Main", "WH-2"), ("Other", "WH-1")):
        with pytest.raises(WarehouseAlreadyExistsError):
            warehouse_service.create_warehouse(WarehouseCreate(name=name, code=code))


def test_update_and_delete(warehouse_service):
    item = warehouse_service.create_warehouse(WarehouseCreate(name="Main", code="WH-1"))
    changed = warehouse_service.update_warehouse(item.id, WarehouseUpdate(name="Second", is_active=False))
    assert changed.name == "Second" and changed.is_active is False
    warehouse_service.delete_warehouse(item.id)
    with pytest.raises(WarehouseNotFoundError):
        warehouse_service.get_warehouse(item.id)


def test_invalid_inputs():
    for data in ({"name": " ", "code": "WH"}, {"name": "Main", "code": " "}):
        with pytest.raises(ValidationError):
            WarehouseCreate(**data)
    with pytest.raises(ValidationError):
        WarehouseUpdate(name=None)
    with pytest.raises(ValidationError):
        WarehouseUpdate(is_active=None)
