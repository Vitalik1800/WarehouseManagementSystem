import pytest

from sqlalchemy.orm import Session

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
