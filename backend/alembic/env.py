import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base
from config import settings
import models  # Ensure all models are registered

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set dynamic sqlalchemy.url from config or settings fallback
# Priority:
# 1. Environment variable DATABASE_URL (if explicitly provided in shell or .env)
# 2. Programmatic override or valid configured option in alembic.ini
# 3. settings.DATABASE_URL fallback if not configured or set to template placeholder 'driver://...'
if os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
else:
    current_url = config.get_main_option("sqlalchemy.url")
    if not current_url or current_url.startswith("driver://"):
        config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if os.getenv("DATABASE_URL"):
        url = settings.DATABASE_URL
    elif not url or url.startswith("driver://"):
        url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    target_url = config.get_main_option("sqlalchemy.url")
    if os.getenv("DATABASE_URL"):
        target_url = settings.DATABASE_URL
    elif not target_url or target_url.startswith("driver://"):
        target_url = settings.DATABASE_URL
    configuration["sqlalchemy.url"] = target_url

    connect_args = {"check_same_thread": False} if target_url.startswith("sqlite") else {}
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
