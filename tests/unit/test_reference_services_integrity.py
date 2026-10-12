from unittest.mock import Mock

import pytest
from pymysql.err import IntegrityError as PyMySQLIntegrityError
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.categories import (
    CategoryCreate,
    CategoryUpdate
)
from backend.app.schemas.storage_locations import (
    StorageLocationCreate,
    StorageLocationUpdate
)

from backend.app.services.category_service import (
    CategoryAlreadyExistsError,
    CategoryInUseError,
    CategoryService,
)
from backend.app.services.supplier_service import (
    SupplierInUseError,
    SupplierService,
)
from backend.app.services.storage_location_service import (
    StorageLocationAlreadyExistsError,
    StorageLocationInUseError,
    StorageLocationService,
)


def make_integrity_error(code: int) -> IntegrityError:
    return IntegrityError(
        statement="TEST",
        params={},
        orig=PyMySQLIntegrityError(
            code,
            "Test integrity error",
        ),
    )


@pytest.mark.parametrize(
    ("code", "expected_exception"),
    [
        (1062, CategoryAlreadyExistsError),
        (1048, IntegrityError),
        (1452, IntegrityError),
    ],
)
def test_category_create_integrity_error(
        code: int,
        expected_exception: type[Exception],
) -> None:
    db = Mock()
    service = CategoryService(db)

    service.categories.get_by_name = Mock(return_value=None)
    service.categories.create = Mock(return_value=Mock())

    db.commit.side_effect = make_integrity_error(code)

    with pytest.raises(expected_exception):
        service.create_category(
            CategoryCreate(name="Electronics")
        )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("code", "expected_exception"),
    [
        (1062, StorageLocationAlreadyExistsError),
        (1048, IntegrityError),
        (1452, IntegrityError),
    ],
)
def test_location_create_integrity_error(
        code: int,
        expected_exception: type[Exception],
) -> None:
    db = Mock()
    service = StorageLocationService(db)

    service.locations.get_by_name = Mock(return_value=None)
    service.locations.create = Mock(return_value=Mock())

    db.commit.side_effect = make_integrity_error(code)

    with pytest.raises(expected_exception):
        service.create_location(
            StorageLocationCreate(name="Warehouse A")
        )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("service_class", "repository_name", "exception_class"),
    [
        (CategoryService, "categories", CategoryInUseError),
        (
                SupplierService,
                "suppliers",
                SupplierInUseError,
        ),
        (
                StorageLocationService,
                "locations",
                StorageLocationInUseError,
        ),
    ],
)
@pytest.mark.parametrize(
    ("code", "expected_business_error"),
    [
        (1451, True),
        (1062, False),
        (1048, False),
    ],
)
def test_reference_delete_integrity_error(
        service_class: type,
        repository_name: str,
        exception_class: type[Exception],
        code: int,
        expected_business_error: bool,
) -> None:
    db = Mock()
    service = service_class(db)

    repository = getattr(service, repository_name)
    entity = Mock(id=1)

    repository.get_by_id = Mock(return_value=entity)
    repository.delete = Mock()

    if repository_name == "suppliers":
        repository.has_stock_movements = Mock(
            return_value=False
        )
        delete_method = service.delete_supplier

    elif repository_name == "categories":
        repository.has_products = Mock(return_value=False)
        delete_method = service.delete_category

    else:
        repository.has_products = Mock(return_value=False)
        delete_method = service.delete_location

    db.commit.side_effect = make_integrity_error(code)

    expected_exception = (
        exception_class
        if expected_business_error
        else IntegrityError
    )

    with pytest.raises(expected_exception):
        delete_method(1)

    repository.delete.assert_called_once_with(entity)
    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("code", "expected_exception"),
    [
        (1062, CategoryAlreadyExistsError),
        (1048, IntegrityError),
        (1452, IntegrityError),
    ],
)
def test_category_update_integrity_error(
        code: int,
        expected_exception: type[Exception],
) -> None:
    db = Mock()
    service = CategoryService(db)

    category = Mock(
        id=1,
        name="Original Category",
        description=None,
    )

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.get_by_name = Mock(
        return_value=None
    )

    db.commit.side_effect = make_integrity_error(code)

    with pytest.raises(expected_exception):
        service.update_category(
            category_id=1,
            data=CategoryUpdate(name="Updated Category"),
        )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("code", "expected_exception"),
    [
        (1062, StorageLocationAlreadyExistsError),
        (1048, IntegrityError),
        (1452, IntegrityError),
    ],
)
def test_location_update_integrity_error(
        code: int,
        expected_exception: type[Exception],
) -> None:
    db = Mock()
    service = StorageLocationService(db)

    location = Mock(
        id=1,
        name="Original Location",
        description=None,
    )

    service.locations.get_by_id = Mock(
        return_value=location
    )
    service.locations.get_by_name = Mock(
        return_value=None
    )

    db.commit.side_effect = make_integrity_error(code)

    with pytest.raises(expected_exception):
        service.update_location(
            location_id=1,
            data=StorageLocationUpdate(name="Updated Location"),
        )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()
