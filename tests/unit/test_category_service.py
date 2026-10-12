from unittest.mock import Mock

import pytest

from backend.app.schemas.categories import (
    CategoryCreate,
    CategoryUpdate
)
from backend.app.services.category_service import (
    CategoryAlreadyExistsError,
    CategoryInUseError,
    CategoryNotFoundError,
    CategoryService
)


def make_service():
    db = Mock()
    service = CategoryService(db)
    return db, service


def make_category(
    category_id=1,
    name="Electronics",
    description="Electronic products",
):
    category = Mock()
    category.id = category_id
    category.name = name
    category.description = description

    return category

# ============================================================
# CREATE
# ============================================================


def test_create_category_success():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_name = Mock(return_value=None)
    service.categories.create = Mock(return_value=category)

    result = service.create_category(
        CategoryCreate(
            name="Electronics",
            description="Electronic products",
        )
    )

    assert result is category

    service.categories.get_by_name.assert_called_once_with(
        "Electronics"
    )
    service.categories.create.assert_called_once_with(
        name="Electronics",
        description="Electronic products",
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(category)
    db.rollback.assert_not_called()


def test_create_category_without_description():
    db, service = make_service()
    category = make_category(description=None)

    service.categories.get_by_name = Mock(return_value=None)
    service.categories.create = Mock(return_value=category)

    result = service.create_category(
        CategoryCreate(name="Electronics")
    )

    assert result is category

    service.categories.create.assert_called_once_with(
        name="Electronics",
        description=None,
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(category)
    db.rollback.assert_not_called()


def test_create_category_duplicate_name():
    db, service = make_service()

    service.categories.get_by_name = Mock(
        return_value=make_category()
    )
    service.categories.create = Mock()

    with pytest.raises(CategoryAlreadyExistsError):
        service.create_category(
            CategoryCreate(name="Electronics")
        )

    service.categories.create.assert_not_called()
    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_create_category_unexpected_database_error():
    db, service = make_service()

    service.categories.get_by_name = Mock(return_value=None)
    service.categories.create = Mock(
        side_effect=RuntimeError("Database unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="Database unavailable",
    ):
        service.create_category(
            CategoryCreate(name="Electronics")
        )

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


# ============================================================
# UPDATE
# ============================================================


def test_update_category_name_success():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.get_by_name = Mock(
        return_value=None
    )

    result = service.update_category(
        category_id=1,
        data=CategoryUpdate(name="Computers"),
    )

    assert result is category
    assert category.name == "Computers"

    service.categories.get_by_name.assert_called_once_with(
        "Computers"
    )

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(category)
    db.rollback.assert_not_called()


def test_update_category_description_success():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.get_by_name = Mock()

    result = service.update_category(
        category_id=1,
        data=CategoryUpdate(
            description="Updated description"
        ),
    )

    assert result is category
    assert category.description == "Updated description"

    service.categories.get_by_name.assert_not_called()

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(category)
    db.rollback.assert_not_called()


def test_update_category_not_found():
    db, service = make_service()

    service.categories.get_by_id = Mock(
        return_value=None
    )

    with pytest.raises(CategoryNotFoundError):
        service.update_category(
            category_id=999,
            data=CategoryUpdate(name="Computers"),
        )

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_category_empty_payload():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )

    result = service.update_category(
        category_id=1,
        data=CategoryUpdate(),
    )

    assert result is category

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_category_same_name():
    db, service = make_service()
    category = make_category(name="Electronics")

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.get_by_name = Mock()

    result = service.update_category(
        category_id=1,
        data=CategoryUpdate(name="Electronics"),
    )

    assert result is category
    assert category.name == "Electronics"

    service.categories.get_by_name.assert_not_called()

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(category)
    db.rollback.assert_not_called()


def test_update_category_duplicate_name():
    db, service = make_service()
    category = make_category()

    competing_category = make_category(
        category_id=2,
        name="Computers",
    )

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.get_by_name = Mock(
        return_value=competing_category
    )

    with pytest.raises(CategoryAlreadyExistsError):
        service.update_category(
            category_id=1,
            data=CategoryUpdate(name="Computers"),
        )

    assert category.name == "Electronics"

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_update_category_unexpected_database_error():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )

    db.commit.side_effect = RuntimeError(
        "Database unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Database unavailable",
    ):
        service.update_category(
            category_id=1,
            data=CategoryUpdate(
                description="Updated description"
            ),
        )

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_category_success():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.has_products = Mock(
        return_value=False
    )
    service.categories.delete = Mock()

    result = service.delete_category(1)

    assert result is None

    service.categories.get_by_id.assert_called_once_with(1)
    service.categories.has_products.assert_called_once_with(1)
    service.categories.delete.assert_called_once_with(category)

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_delete_category_not_found():
    db, service = make_service()

    service.categories.get_by_id = Mock(
        return_value=None
    )
    service.categories.has_products = Mock()
    service.categories.delete = Mock()

    with pytest.raises(CategoryNotFoundError):
        service.delete_category(999)

    service.categories.has_products.assert_not_called()
    service.categories.delete.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_delete_category_with_products():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.has_products = Mock(
        return_value=True
    )
    service.categories.delete = Mock()

    with pytest.raises(CategoryInUseError):
        service.delete_category(1)

    service.categories.delete.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_delete_category_unexpected_database_error():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.has_products = Mock(
        return_value=False
    )
    service.categories.delete = Mock()

    db.commit.side_effect = RuntimeError(
        "Database unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="Database unavailable",
    ):
        service.delete_category(1)

    service.categories.delete.assert_called_once_with(category)

    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_delete_category_repository_error():
    db, service = make_service()
    category = make_category()

    service.categories.get_by_id = Mock(
        return_value=category
    )
    service.categories.has_products = Mock(
        return_value=False
    )
    service.categories.delete = Mock(
        side_effect=RuntimeError("Delete failed")
    )

    with pytest.raises(
        RuntimeError,
        match="Delete failed",
    ):
        service.delete_category(1)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
