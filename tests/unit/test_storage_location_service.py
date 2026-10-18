from unittest.mock import Mock

import pytest

from backend.app.schemas.storage_locations import (
    StorageLocationCreate,
    StorageLocationUpdate,
)
from backend.app.services.storage_location_service import (
    StorageLocationAlreadyExistsError,
    StorageLocationInUseError,
    StorageLocationNotFoundError,
    StorageLocationWarehouseNotFoundError,
    StorageLocationService,
)


def make_service():
    db = Mock()
    service = StorageLocationService(db)
    warehouse = Mock()
    warehouse.id = 7
    service.warehouses.get_by_code = Mock(return_value=warehouse)
    return db, service


def make_location(
    location_id=1,
    name="Warehouse A",
    description="Main warehouse",
):
    location = Mock()
    location.id = location_id
    location.name = name
    location.description = description
    return location


# ============================================================
# GET
# ============================================================


def test_get_location_success():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )

    result = service.get_location(1)

    assert result is location
    service.locations.get_by_id.assert_called_once_with(1)

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_location_not_found():
    db, service = make_service()

    service.locations.get_by_id = Mock(
        return_value=None
    )

    with pytest.raises(StorageLocationNotFoundError):
        service.get_location(999)

    service.locations.get_by_id.assert_called_once_with(999)

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


# ============================================================
# LIST
# ============================================================


def test_list_locations_default_pagination():
    db, service = make_service()

    locations = [
        make_location(1, "Warehouse A"),
        make_location(2, "Warehouse B"),
    ]

    service.locations.get_all = Mock(
        return_value=locations
    )

    result = service.list_locations()

    assert result == locations

    service.locations.get_all.assert_called_once_with(
        offset=0,
        limit=50,
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_list_locations_custom_pagination():
    db, service = make_service()

    locations = [
        make_location(11, "Warehouse K"),
    ]

    service.locations.get_all = Mock(
        return_value=locations
    )

    result = service.list_locations(
        offset=10,
        limit=5,
    )

    assert result == locations

    service.locations.get_all.assert_called_once_with(
        offset=10,
        limit=5,
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


# ============================================================
# CREATE
# ============================================================


def test_create_location_success():
    db, service = make_service()
    location = make_location()

    data = StorageLocationCreate(
        name="Warehouse A",
        description="Main warehouse",
    )

    service.locations.get_by_name = Mock(
        return_value=None
    )
    service.locations.create = Mock(
        return_value=location
    )

    result = service.create_location(data)

    assert result is location

    service.locations.get_by_name.assert_called_once_with(
        "Warehouse A"
    )
    service.locations.create.assert_called_once_with(
        **data.model_dump(exclude={'warehouse_id'}),
        warehouse_id=7,
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(location)
    db.rollback.assert_not_called()


def test_create_location_without_description():
    db, service = make_service()
    location = make_location(description=None)

    data = StorageLocationCreate(name="Warehouse A")

    service.locations.get_by_name = Mock(
        return_value=None
    )
    service.locations.create = Mock(
        return_value=location
    )

    result = service.create_location(data)

    assert result is location

    service.locations.create.assert_called_once_with(
        **data.model_dump(exclude={'warehouse_id'}),
        warehouse_id=7,
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(location)
    db.rollback.assert_not_called()


def test_create_location_duplicate_name():
    db, service = make_service()

    service.locations.get_by_name = Mock(
        return_value=make_location()
    )
    service.locations.create = Mock()

    with pytest.raises(StorageLocationAlreadyExistsError):
        service.create_location(
            StorageLocationCreate(name="Warehouse A")
        )

    service.locations.create.assert_not_called()

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_create_location_repository_error():
    db, service = make_service()

    service.locations.get_by_name = Mock(
        return_value=None
    )
    service.locations.create = Mock(
        side_effect=RuntimeError("Repository failure")
    )

    with pytest.raises(
        RuntimeError,
        match="Repository failure",
    ):
        service.create_location(
            StorageLocationCreate(name="Warehouse A")
        )

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


def test_create_location_with_explicit_warehouse():
    db, service = make_service()
    location = make_location()
    warehouse = Mock()
    warehouse.id = 12

    service.locations.get_by_name = Mock(return_value=None)
    service.locations.create = Mock(return_value=location)
    service.warehouses.get_by_id = Mock(return_value=warehouse)

    data = StorageLocationCreate(
        name="Warehouse A",
        warehouse_id=12,
    )

    result = service.create_location(data)

    assert result is location
    service.warehouses.get_by_id.assert_called_once_with(12)
    service.warehouses.get_by_code.assert_not_called()
    service.locations.create.assert_called_once_with(
        name="Warehouse A",
        description=None,
        warehouse_id=12,
    )
    db.commit.assert_called_once()


def test_create_location_with_unknown_warehouse():
    db, service = make_service()

    service.locations.get_by_name = Mock(return_value=None)
    service.warehouses.get_by_id = Mock(return_value=None)
    service.locations.create = Mock()

    with pytest.raises(
        StorageLocationWarehouseNotFoundError,
        match="Warehouse not found",
    ):
        service.create_location(
            StorageLocationCreate(
                name="Warehouse A",
                warehouse_id=999999,
            )
        )

    service.warehouses.get_by_id.assert_called_once_with(999999)
    service.locations.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_create_location_without_main_warehouse():
    db, service = make_service()

    service.locations.get_by_name = Mock(return_value=None)
    service.warehouses.get_by_code = Mock(return_value=None)
    service.locations.create = Mock()

    with pytest.raises(
        StorageLocationWarehouseNotFoundError,
        match="Warehouse not found",
    ):
        service.create_location(
            StorageLocationCreate(name="Warehouse A")
        )

    service.warehouses.get_by_code.assert_called_once_with("MAIN")
    service.locations.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


# ============================================================
# UPDATE
# ============================================================


def test_update_location_name_success():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.get_by_name = Mock(
        return_value=None
    )

    result = service.update_location(
        location_id=1,
        data=StorageLocationUpdate(name="Warehouse B"),
    )

    assert result is location
    assert location.name == "Warehouse B"

    service.locations.get_by_name.assert_called_once_with(
        "Warehouse B"
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(location)
    db.rollback.assert_not_called()


def test_update_location_description_success():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.get_by_name = Mock()

    result = service.update_location(
        location_id=1,
        data=StorageLocationUpdate(
            description="Updated description"
        ),
    )

    assert result is location
    assert location.description == "Updated description"

    service.locations.get_by_name.assert_not_called()

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(location)
    db.rollback.assert_not_called()


def test_update_location_not_found():
    db, service = make_service()

    service.locations.get_by_id = Mock(
        return_value=None
    )

    with pytest.raises(StorageLocationNotFoundError):
        service.update_location(
            location_id=999,
            data=StorageLocationUpdate(name="Warehouse B"),
        )

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_location_empty_payload():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )

    result = service.update_location(
        location_id=1,
        data=StorageLocationUpdate(),
    )

    assert result is location

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_location_same_name():
    db, service = make_service()
    location = make_location(
        location_id=1,
        name="Warehouse A",
    )

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.get_by_name = Mock(
        return_value=location
    )

    result = service.update_location(
        location_id=1,
        data=StorageLocationUpdate(name="Warehouse A"),
    )

    assert result is location
    assert location.name == "Warehouse A"

    service.locations.get_by_name.assert_called_once_with(
        "Warehouse A"
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(location)
    db.rollback.assert_not_called()


def test_update_location_duplicate_name():
    db, service = make_service()
    location = make_location()

    competing_location = make_location(
        location_id=2,
        name="Warehouse B",
    )

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.get_by_name = Mock(
        return_value=competing_location
    )

    with pytest.raises(StorageLocationAlreadyExistsError):
        service.update_location(
            location_id=1,
            data=StorageLocationUpdate(name="Warehouse B"),
        )

    assert location.name == "Warehouse A"

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_location_commit_error():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )

    db.commit.side_effect = RuntimeError(
        "Commit failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Commit failure",
    ):
        service.update_location(
            location_id=1,
            data=StorageLocationUpdate(
                description="Updated description"
            ),
        )

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


def test_update_location_refresh_error():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )

    db.refresh.side_effect = RuntimeError(
        "Refresh failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Refresh failure",
    ):
        service.update_location(
            location_id=1,
            data=StorageLocationUpdate(
                description="Updated description"
            ),
        )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(location)
    db.rollback.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_location_success():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.has_products = Mock(
        return_value=False
    )
    service.locations.delete = Mock()

    result = service.delete_location(1)

    assert result is None

    service.locations.get_by_id.assert_called_once_with(1)
    service.locations.has_products.assert_called_once_with(1)
    service.locations.delete.assert_called_once_with(location)

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_delete_location_not_found():
    db, service = make_service()

    service.locations.get_by_id = Mock(
        return_value=None
    )
    service.locations.has_products = Mock()
    service.locations.delete = Mock()

    with pytest.raises(StorageLocationNotFoundError):
        service.delete_location(999)

    service.locations.has_products.assert_not_called()
    service.locations.delete.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_delete_location_with_products():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.has_products = Mock(
        return_value=True
    )
    service.locations.delete = Mock()

    with pytest.raises(StorageLocationInUseError):
        service.delete_location(1)

    service.locations.delete.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_delete_location_commit_error():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.has_products = Mock(
        return_value=False
    )
    service.locations.delete = Mock()

    db.commit.side_effect = RuntimeError(
        "Commit failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Commit failure",
    ):
        service.delete_location(1)

    service.locations.delete.assert_called_once_with(location)

    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_delete_location_repository_error():
    db, service = make_service()
    location = make_location()

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.has_products = Mock(
        return_value=False
    )
    service.locations.delete = Mock(
        side_effect=RuntimeError("Delete failure")
    )

    with pytest.raises(
        RuntimeError,
        match="Delete failure",
    ):
        service.delete_location(1)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
