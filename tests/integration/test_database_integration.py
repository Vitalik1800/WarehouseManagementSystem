
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.app.db.session import engine
from backend.app.models import (
    Category,
    Product,
    StockMovement,
    StorageLocation,
    Supplier,
    User,
)


@pytest.fixture
def db_session():
    """Кожен тест виконується в транзакції з подальшим відкатом."""
    with engine.connect() as connection:
        transaction = connection.begin()

        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()


def unique_value(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def create_sample_records(db: Session):
    category = Category(
        name=unique_value("Category"),
        description="Категорія для інтеграційного тестування",
    )

    location = StorageLocation(
        name=unique_value("Location"),
        description="Місце зберігання для інтеграційного тестування",
    )

    supplier = Supplier(
        name=unique_value("Supplier"),
        email="supplier@example.com",
    )

    user = User(
        name="Користувач інтеграційного тестування",
        username=unique_value("testuser"),
        password_hash="test_hash_not_a_real_password",
        role="worker",
        is_active=True,
    )

    db.add_all([category, location, supplier, user])
    db.flush()

    product = Product(
        sku=unique_value("SKU"),
        name="Товар для інтеграційного тестування",
        unit="pcs",
        quantity=Decimal("25.000"),
        category_id=category.id,
        location_id=location.id,
    )

    db.add(product)
    db.flush()

    return category, location, supplier, user, product


def test_all_database_tables_exist():
    inspector = inspect(engine)

    expected = {
        "alembic_version",
        "categories",
        "products",
        "stock_movements",
        "storage_locations",
        "suppliers",
        "users",
    }

    assert expected.issubset(set(inspector.get_table_names()))


def test_create_and_read_orm_records(db_session):
    category, location, supplier, user, product = (
        create_sample_records(db_session)
    )

    loaded_product = db_session.get(Product, product.id)

    assert loaded_product is not None
    assert loaded_product.name == "Товар для інтеграційного тестування"
    assert loaded_product.quantity == Decimal("25.000")
    assert loaded_product.category.name == category.name
    assert loaded_product.location.name == location.name


def test_stock_movement_relationships(db_session):
    category, location, supplier, user, product = (
        create_sample_records(db_session)
    )

    movement = StockMovement(
        product_id=product.id,
        user_id=user.id,
        supplier_id=supplier.id,
        movement_type="receipt",
        quantity=Decimal("5.000"),
        note="Тестове надходження товару",
    )

    db_session.add(movement)
    db_session.flush()

    loaded = db_session.get(StockMovement, movement.id)

    assert loaded is not None
    assert loaded.product.id == product.id
    assert loaded.user.id == user.id
    assert loaded.supplier.id == supplier.id
    assert loaded.quantity == Decimal("5.000")


def test_unique_sku_constraint(db_session):
    category, location, supplier, user, product = (
        create_sample_records(db_session)
    )

    duplicate = Product(
        sku=product.sku,
        name="Дублікат артикулу",
        unit="pcs",
        quantity=Decimal("1.000"),
        category_id=category.id,
        location_id=location.id,
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_negative_product_quantity_rejected(db_session):
    category, location, supplier, user, product = (
        create_sample_records(db_session)
    )

    product.quantity = Decimal("-1.000")

    with pytest.raises(OperationalError) as exc_info:
        db_session.flush()

    assert exc_info.value.orig.args[0] == 3819


def test_invalid_movement_type_rejected(db_session):
    category, location, supplier, user, product = (
        create_sample_records(db_session)
    )

    movement = StockMovement(
        product_id=product.id,
        user_id=user.id,
        movement_type="invalid",
        quantity=Decimal("1.000"),
    )

    db_session.add(movement)

    with pytest.raises(OperationalError) as exc_info:
        db_session.flush()

    assert exc_info.value.orig.args[0] == 3819


def test_foreign_key_restrict(db_session):
    category, location, supplier, user, product = (
        create_sample_records(db_session)
    )

    movement = StockMovement(
        product_id=product.id,
        user_id=user.id,
        movement_type="issue",
        quantity=Decimal("1.000"),
    )

    db_session.add(movement)
    db_session.flush()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text("DELETE FROM products WHERE id = :product_id"),
            {"product_id": product.id},
        )


def test_transaction_rollback():
    marker = unique_value("RollbackCategory")

    with engine.connect() as connection:
        transaction = connection.begin()

        try:
            connection.execute(
                text(
                    "INSERT INTO categories (name, description) "
                    "VALUES (:name, :description)"
                ),
                {
                    "name": marker,
                    "description": "Перевірка відкочування транзакції",
                },
            )
        finally:
            transaction.rollback()

    with Session(engine) as session:
        result = session.scalar(
            select(Category).where(Category.name == marker)
        )

        assert result is None
