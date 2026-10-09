from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

from backend.app.core.config import get_settings


TEST_DATABASE_NAME = "warehouse_test_db"


def create_test_engine() -> Engine:
    """Створює підключення виключно до тестової MySQL-бази."""

    settings = get_settings()

    main_url = make_url(
        settings.database_url.get_secret_value()
    )

    if main_url.get_backend_name() != "mysql":
        raise RuntimeError(
            "Integration tests require a MySQL database"
        )

    if main_url.database == TEST_DATABASE_NAME:
        raise RuntimeError(
            "Application DATABASE_URL must not point to the test database"
        )

    test_url = main_url.set(
        database=TEST_DATABASE_NAME
    )

    if test_url.database != TEST_DATABASE_NAME:
        raise RuntimeError(
            "Unsafe test database configuration"
        )

    return create_engine(
        test_url,
        pool_pre_ping=True,
        echo=False
    )
