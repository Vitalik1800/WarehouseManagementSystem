from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import backend.app.models
from backend.app.core.config import get_settings
from backend.app.db.base import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)



settings = get_settings()

migration_args = context.get_x_argument(as_dictionary=True)

database_url = migration_args.get(
    "db_url",
    settings.database_url.get_secret_value()
)

if "db_url" in migration_args:
    from sqlalchemy.engine import make_url

    parsed_url = make_url(database_url)

    if (
        parsed_url.get_backend_name() != "mysql"
        or parsed_url.database != "warehouse_test_db"
    ):
        raise RuntimeError(
            "Explicit migration URL must target warehouse_test_db"
        )

config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
