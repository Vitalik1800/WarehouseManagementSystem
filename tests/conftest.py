import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import engine


@pytest.fixture
def db_session():
    """Створює ізольовану транзакцію MySQL для кожного тесту."""
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
