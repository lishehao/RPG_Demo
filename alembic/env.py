from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from rpg_backend.config.settings import get_settings
from rpg_backend.storage import models  # noqa: F401

config = context.config


def _normalize_database_url(value: str) -> str:
    database_url = (value or "").strip()
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    env_url = os.getenv("APP_DATABASE_URL")
    if env_url:
        return _normalize_database_url(env_url)
    return _normalize_database_url(get_settings().database_url)


config.set_main_option("sqlalchemy.url", _database_url())

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
