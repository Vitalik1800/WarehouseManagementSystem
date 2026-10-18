import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.warehouse import Warehouse

from tests.db_config import create_test_engine


@pytest.fixture(scope="session")
def test_engine():
    """Створює SQLAlchemy Engine для тестової бази."""
    engine = create_test_engine()

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Створює ізольовану транзакцію для кожного тесту."""
    with test_engine.connect() as connection:
        transaction = connection.begin()

        try:
            with Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ) as session:
                yield session
        finally:
            transaction.rollback()



@pytest.fixture
def main_warehouse_id(db_session):
    """Return the MAIN warehouse ID from the isolated test database."""
    warehouse_id = db_session.scalar(
        select(Warehouse.id).where(Warehouse.code == "MAIN")
    )

    if warehouse_id is None:
        pytest.fail(
            "MAIN warehouse is missing from the test database. "
            "Check the test database migration and seed data."
        )

    return warehouse_id
