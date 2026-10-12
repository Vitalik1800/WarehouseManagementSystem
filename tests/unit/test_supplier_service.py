from unittest.mock import Mock

import pytest

from backend.app.schemas.suppliers import (
    SupplierCreate,
    SupplierUpdate,
)
from backend.app.services.supplier_service import (
    SupplierInUseError,
    SupplierNotFoundError,
    SupplierService,
)


def make_service():
    db = Mock()
    service = SupplierService(db)
    return db, service


def make_supplier(
    supplier_id=1,
    name="Test Supplier",
):
    supplier = Mock()
    supplier.id = supplier_id
    supplier.name = name
    return supplier


def make_create_data():
    return SupplierCreate(name="Test Supplier")


# ============================================================
# GET
# ============================================================


def test_get_supplier_success():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )

    result = service.get_supplier(1)

    assert result is supplier

    service.suppliers.get_by_id.assert_called_once_with(1)

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_get_supplier_not_found():
    db, service = make_service()

    service.suppliers.get_by_id = Mock(
        return_value=None
    )

    with pytest.raises(SupplierNotFoundError):
        service.get_supplier(999)

    service.suppliers.get_by_id.assert_called_once_with(999)

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


# ============================================================
# LIST
# ============================================================


def test_list_suppliers_default_pagination():
    db, service = make_service()

    suppliers = [
        make_supplier(1, "Supplier A"),
        make_supplier(2, "Supplier B"),
    ]

    service.suppliers.get_all = Mock(
        return_value=suppliers
    )

    result = service.list_suppliers()

    assert result == suppliers

    service.suppliers.get_all.assert_called_once_with(
        offset=0,
        limit=50,
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_list_suppliers_custom_pagination():
    db, service = make_service()

    suppliers = [
        make_supplier(11, "Supplier K"),
    ]

    service.suppliers.get_all = Mock(
        return_value=suppliers
    )

    result = service.list_suppliers(
        offset=10,
        limit=5,
    )

    assert result == suppliers

    service.suppliers.get_all.assert_called_once_with(
        offset=10,
        limit=5,
    )

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


# ============================================================
# CREATE
# ============================================================


def test_create_supplier_success():
    db, service = make_service()
    supplier = make_supplier()

    data = make_create_data()

    service.suppliers.create = Mock(
        return_value=supplier
    )

    result = service.create_supplier(data)

    assert result is supplier

    service.suppliers.create.assert_called_once_with(
        **data.model_dump()
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(supplier)
    db.rollback.assert_not_called()


def test_create_supplier_repository_error():
    db, service = make_service()

    service.suppliers.create = Mock(
        side_effect=RuntimeError("Repository failure")
    )

    with pytest.raises(
        RuntimeError,
        match="Repository failure",
    ):
        service.create_supplier(make_create_data())

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


def test_create_supplier_commit_error():
    db, service = make_service()

    service.suppliers.create = Mock(
        return_value=make_supplier()
    )

    db.commit.side_effect = RuntimeError(
        "Commit failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Commit failure",
    ):
        service.create_supplier(make_create_data())

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


# ============================================================
# UPDATE
# ============================================================


def test_update_supplier_success():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )

    result = service.update_supplier(
        supplier_id=1,
        data=SupplierUpdate(name="Updated Supplier"),
    )

    assert result is supplier
    assert supplier.name == "Updated Supplier"

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(supplier)
    db.rollback.assert_not_called()


def test_update_supplier_not_found():
    db, service = make_service()

    service.suppliers.get_by_id = Mock(
        return_value=None
    )

    with pytest.raises(SupplierNotFoundError):
        service.update_supplier(
            supplier_id=999,
            data=SupplierUpdate(name="Updated Supplier"),
        )

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_supplier_empty_payload():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )

    result = service.update_supplier(
        supplier_id=1,
        data=SupplierUpdate(),
    )

    assert result is supplier

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_supplier_commit_error():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )

    db.commit.side_effect = RuntimeError(
        "Commit failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Commit failure",
    ):
        service.update_supplier(
            supplier_id=1,
            data=SupplierUpdate(name="Updated Supplier"),
        )

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


def test_update_supplier_refresh_error():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )

    db.refresh.side_effect = RuntimeError(
        "Refresh failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Refresh failure",
    ):
        service.update_supplier(
            supplier_id=1,
            data=SupplierUpdate(name="Updated Supplier"),
        )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(supplier)
    db.rollback.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_supplier_success():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )
    service.suppliers.has_stock_movements = Mock(
        return_value=False
    )
    service.suppliers.delete = Mock()

    result = service.delete_supplier(1)

    assert result is None

    service.suppliers.get_by_id.assert_called_once_with(1)
    service.suppliers.has_stock_movements.assert_called_once_with(1)
    service.suppliers.delete.assert_called_once_with(supplier)

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_delete_supplier_not_found():
    db, service = make_service()

    service.suppliers.get_by_id = Mock(
        return_value=None
    )
    service.suppliers.has_stock_movements = Mock()
    service.suppliers.delete = Mock()

    with pytest.raises(SupplierNotFoundError):
        service.delete_supplier(999)

    service.suppliers.has_stock_movements.assert_not_called()
    service.suppliers.delete.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_delete_supplier_with_stock_movements():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )
    service.suppliers.has_stock_movements = Mock(
        return_value=True
    )
    service.suppliers.delete = Mock()

    with pytest.raises(SupplierInUseError):
        service.delete_supplier(1)

    service.suppliers.delete.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_delete_supplier_commit_error():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )
    service.suppliers.has_stock_movements = Mock(
        return_value=False
    )
    service.suppliers.delete = Mock()

    db.commit.side_effect = RuntimeError(
        "Commit failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Commit failure",
    ):
        service.delete_supplier(1)

    service.suppliers.delete.assert_called_once_with(supplier)

    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_delete_supplier_repository_error():
    db, service = make_service()
    supplier = make_supplier()

    service.suppliers.get_by_id = Mock(
        return_value=supplier
    )
    service.suppliers.has_stock_movements = Mock(
        return_value=False
    )
    service.suppliers.delete = Mock(
        side_effect=RuntimeError("Delete failure")
    )

    with pytest.raises(
        RuntimeError,
        match="Delete failure",
    ):
        service.delete_supplier(1)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
