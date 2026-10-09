from alembic import command
from alembic.config import Config
from sqlalchemy import text

from tests.db_config import create_test_engine


TEST_DATABASE_NAME = "warehouse_test_db"


def main() -> None:
    engine = create_test_engine()

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT DATABASE()")
            ).scalar_one()

        if database_name != TEST_DATABASE_NAME:
            raise RuntimeError(
                "Migration aborted: unsafe database target"
            )

        config = Config("alembic.ini")

        # Передаємо підключення безпосередньо через об'єкт
        # конфігурації, не виводячи пароль у консоль.
        config.attributes["test_database_url"] = (
            engine.url.render_as_string(
                hide_password=False
            )
        )

        # env.py очікує -x db_url=..., тому передаємо
        # параметр програмно.
        config.cmd_opts = type(
            "Options",
            (),
            {
                "x": [
                    "db_url="
                    + config.attributes["test_database_url"]
                ]
            }
        )()

        command.upgrade(config, "head")

        print("TEST DATABASE MIGRATIONS COMPLETED")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
