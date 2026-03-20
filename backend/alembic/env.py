"""Alembic migration environment."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models so Alembic can detect them
from app.database import Base
from app.models import *  # noqa: F401,F403

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from environment
pg_user = os.getenv("POSTGRES_USER", "aiwt")
pg_pass = os.getenv("POSTGRES_PASSWORD", "changeme")
pg_host = os.getenv("POSTGRES_HOST", "localhost")
pg_port = os.getenv("POSTGRES_PORT", "5432")
pg_db = os.getenv("POSTGRES_DB", "ai_workflow_terminal")
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}",
)


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
