from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.products import ProductCreate, ProductUpdate
from backend.app.services.product_service import (
    ProductAlreadyExistsError,
    ProductCategoryNotFoundError,
    ProductInUseError,
    ProductLocationChangeError,
    ProductLocationNotFoundError,
    ProductNotFoundError,
    ProductService,
)


def make_service():
    db = Mock()
    service = ProductService(db)

    service.products.get_by_sku = Mock(return_value=None)
    service.products.get_by_id = Mock(return_value=None)
    service.products.get_all = Mock(return_value=[])
    service.products.create = Mock()
    service.products.delete = Mock()
    service.products.has_stock_movements = Mock(return_value=False)

    service.categories.get_by_id = Mock(return_value=Mock())
    service.locations.get_by_id = Mock(return_value=Mock())

    return db, service


def make_product(
    product_id=1,
    sku="SKU-001",
    name="Test Product",
    category_id=1,
    location_id=1,
    quantity="0.000",
):
    product = Mock()
    product.id = product_id
    product.sku = sku
    product.name = name
    product.unit = "pcs"
    product.description = None
    product.category_id = category_id
    product.location_id = location_id
    product.quantity = Decimal(quantity)
    return product


def make_create_data(**changes):
    payload = {
        "sku": "SKU-001",
        "name": "Test Product",
        "category_id": 1,
        "location_id": 1,
    }
    payload.update(changes)
    return ProductCreate(**payload)


def make_integrity_error():
    return IntegrityError(
        "INSERT INTO products ...",
        {},
        Exception("Database integrity error"),
    )


# ============================================================
# CREATE
# ============================================================


def test_create_product_success():
    db, service = make_service()
    product = make_product()
    service.products.create.return_value = product

    result = service.create_product(make_create_data())

    assert result is product
    service.products.get_by_sku.assert_called_once_with("SKU-001")
    service.categories.get_by_id.assert_called_once_with(1)
    service.locations.get_by_id.assert_called_once_with(1)

    service.products.create.assert_called_once_with(
        sku="SKU-001",
        name="Test Product",
        unit="pcs",
        description=None,
        category_id=1,
        location_id=1,
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(product)
    db.rollback.assert_not_called()


def test_create_product_duplicate_sku():
    db, service = make_service()
    service.products.get_by_sku.return_value = make_product()

    with pytest.raises(ProductAlreadyExistsError):
        service.create_product(make_create_data())

    service.products.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_create_product_missing_category():
    db, service = make_service()
    service.categories.get_by_id.return_value = None

    with pytest.raises(ProductCategoryNotFoundError):
        service.create_product(make_create_data())

    service.products.create.assert_not_called()
    db.commit.assert_not_called()


def test_create_product_missing_location():
    db, service = make_service()
    service.locations.get_by_id.return_value = None

    with pytest.raises(ProductLocationNotFoundError):
        service.create_product(make_create_data())

    service.products.create.assert_not_called()
    db.commit.assert_not_called()


def test_create_product_repository_error():
    db, service = make_service()
    service.products.create.side_effect = RuntimeError("Create failed")

    with pytest.raises(RuntimeError, match="Create failed"):
        service.create_product(make_create_data())

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_create_product_commit_error():
    db, service = make_service()
    service.products.create.return_value = make_product()
    db.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        service.create_product(make_create_data())

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize(
    ("duplicate", "missing", "expected_error"),
    [
        (True, False, ProductAlreadyExistsError),
        (False, True, ProductCategoryNotFoundError),
    ],
)
def test_create_product_integrity_error_mapping(
    duplicate, missing, expected_error
):
    db, service = make_service()
    service.products.create.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_duplicate_entry",
        return_value=duplicate,
    ), patch(
        "backend.app.services.product_service.is_missing_reference",
        return_value=missing,
    ):
        if missing:
            service.categories.get_by_id.side_effect = [
                Mock(),
                None,
            ]

        with pytest.raises(expected_error):
            service.create_product(make_create_data())

    db.rollback.assert_called_once()


def test_create_product_unknown_integrity_error():
    db, service = make_service()
    service.products.create.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_duplicate_entry",
        return_value=False,
    ), patch(
        "backend.app.services.product_service.is_missing_reference",
        return_value=False,
    ):
        with pytest.raises(IntegrityError):
            service.create_product(make_create_data())

    db.rollback.assert_called_once()


# ============================================================
# GET AND LIST
# ============================================================


def test_get_product_success():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product

    assert service.get_product(1) is product
    service.products.get_by_id.assert_called_once_with(1)


def test_get_product_not_found():
    db, service = make_service()

    with pytest.raises(ProductNotFoundError):
        service.get_product(999)

    service.products.get_by_id.assert_called_once_with(999)


def test_list_products_default():
    db, service = make_service()
    products = [make_product()]
    service.products.get_all.return_value = products

    assert service.list_products() == products

    service.products.get_all.assert_called_once_with(
        offset=0,
        limit=50,
        search=None,
        sku=None,
        category_id=None,
        location_id=None,
    )


def test_list_products_with_filters():
    db, service = make_service()

    service.list_products(
        offset=10,
        limit=20,
        search="phone",
        sku="SKU-001",
        category_id=2,
        location_id=3,
    )

    service.products.get_all.assert_called_once_with(
        offset=10,
        limit=20,
        search="phone",
        sku="SKU-001",
        category_id=2,
        location_id=3,
    )


# ============================================================
# UPDATE
# ============================================================


def test_update_product_name_success():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product

    result = service.update_product(
        1, ProductUpdate(name="Updated Product")
    )

    assert result is product
    assert product.name == "Updated Product"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(product)


def test_update_product_empty_payload():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product

    assert service.update_product(1, ProductUpdate()) is product

    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_update_product_not_found():
    db, service = make_service()

    with pytest.raises(ProductNotFoundError):
        service.update_product(999, ProductUpdate(name="Updated"))

    db.commit.assert_not_called()


def test_update_product_same_sku():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product

    service.update_product(1, ProductUpdate(sku="SKU-001"))

    service.products.get_by_sku.assert_not_called()
    db.commit.assert_called_once()


def test_update_product_duplicate_sku():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product
    service.products.get_by_sku.return_value = make_product(
        product_id=2, sku="SKU-002"
    )

    with pytest.raises(ProductAlreadyExistsError):
        service.update_product(1, ProductUpdate(sku="SKU-002"))

    assert product.sku == "SKU-001"
    db.commit.assert_not_called()


def test_update_product_missing_category():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product
    service.categories.get_by_id.return_value = None

    with pytest.raises(ProductCategoryNotFoundError):
        service.update_product(1, ProductUpdate(category_id=2))

    assert product.category_id == 1
    db.commit.assert_not_called()


def test_update_product_missing_location():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product
    service.locations.get_by_id.return_value = None

    with pytest.raises(ProductLocationNotFoundError):
        service.update_product(1, ProductUpdate(location_id=2))

    assert product.location_id == 1
    db.commit.assert_not_called()


def test_update_product_location_with_stock_forbidden():
    db, service = make_service()
    product = make_product(quantity="5.000")
    service.products.get_by_id.return_value = product

    with pytest.raises(ProductLocationChangeError):
        service.update_product(1, ProductUpdate(location_id=2))

    assert product.location_id == 1
    service.locations.get_by_id.assert_not_called()
    db.commit.assert_not_called()


def test_update_product_location_without_stock():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product

    service.update_product(1, ProductUpdate(location_id=2))

    assert product.location_id == 2
    service.locations.get_by_id.assert_called_once_with(2)
    db.commit.assert_called_once()


def test_update_product_commit_error():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product
    db.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        service.update_product(
            1, ProductUpdate(name="Updated")
        )

    db.rollback.assert_called_once()


def test_update_product_duplicate_integrity_error():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    db.commit.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_duplicate_entry",
        return_value=True,
    ):
        with pytest.raises(ProductAlreadyExistsError):
            service.update_product(
                1, ProductUpdate(name="Updated")
            )

    db.rollback.assert_called_once()


def test_update_product_unknown_integrity_error():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    db.commit.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_duplicate_entry",
        return_value=False,
    ), patch(
        "backend.app.services.product_service.is_missing_reference",
        return_value=False,
    ):
        with pytest.raises(IntegrityError):
            service.update_product(
                1, ProductUpdate(name="Updated")
            )

    db.rollback.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_product_success():
    db, service = make_service()
    product = make_product()
    service.products.get_by_id.return_value = product

    assert service.delete_product(1) is None

    service.products.has_stock_movements.assert_called_once_with(1)
    service.products.delete.assert_called_once_with(product)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_delete_product_not_found():
    db, service = make_service()

    with pytest.raises(ProductNotFoundError):
        service.delete_product(999)

    service.products.delete.assert_not_called()
    db.commit.assert_not_called()


def test_delete_product_with_stock_movements():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    service.products.has_stock_movements.return_value = True

    with pytest.raises(ProductInUseError):
        service.delete_product(1)

    service.products.delete.assert_not_called()
    db.commit.assert_not_called()


def test_delete_product_repository_error():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    service.products.delete.side_effect = RuntimeError("Delete failed")

    with pytest.raises(RuntimeError, match="Delete failed"):
        service.delete_product(1)

    db.rollback.assert_called_once()


def test_delete_product_commit_error():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    db.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        service.delete_product(1)

    db.rollback.assert_called_once()


def test_delete_product_referenced_integrity_error():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    db.commit.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_row_referenced",
        return_value=True,
    ):
        with pytest.raises(ProductInUseError):
            service.delete_product(1)

    db.rollback.assert_called_once()


def test_delete_product_unknown_integrity_error():
    db, service = make_service()
    service.products.get_by_id.return_value = make_product()
    db.commit.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_row_referenced",
        return_value=False,
    ):
        with pytest.raises(IntegrityError):
            service.delete_product(1)

    db.rollback.assert_called_once()


# ============================================================
# ADDITIONAL FOREIGN KEY INTEGRITY ERROR TESTS
# ============================================================


def test_create_product_missing_location_after_integrity_error():
    db, service = make_service()

    service.products.create.side_effect = make_integrity_error()

    # First check succeeds before INSERT.
    # Second check fails after the foreign key error.
    service.locations.get_by_id.side_effect = [
        Mock(),
        None,
    ]

    with patch(
        "backend.app.services.product_service.is_duplicate_entry",
        return_value=False,
    ), patch(
        "backend.app.services.product_service.is_missing_reference",
        return_value=True,
    ):
        with pytest.raises(ProductLocationNotFoundError):
            service.create_product(make_create_data())

    assert service.locations.get_by_id.call_count == 2
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


def test_update_product_missing_reference_integrity_error():
    db, service = make_service()
    product = make_product()

    service.products.get_by_id.return_value = product
    db.commit.side_effect = make_integrity_error()

    with patch(
        "backend.app.services.product_service.is_duplicate_entry",
        return_value=False,
    ), patch(
        "backend.app.services.product_service.is_missing_reference",
        return_value=True,
    ):
        with pytest.raises(IntegrityError):
            service.update_product(
                1,
                ProductUpdate(name="Updated Product"),
            )

    service.categories.get_by_id.assert_called_once_with(1)
    service.locations.get_by_id.assert_called_once_with(1)

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()
