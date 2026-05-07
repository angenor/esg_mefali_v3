"""Configuration Alembic pour migrations async."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models.base import Base

# Importer tous les modèles pour que Alembic les détecte
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Exécuter les migrations en mode 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # noqa: ANN001
    """Exécuter les migrations avec une connexion."""
    # F22 — la colonne alembic_version.version_num est par défaut VARCHAR(32),
    # ce qui devient limitant pour des révisions descriptives (ex. F22 :
    # ``032_add_validation_error_tool_call_logs`` = 39 caractères).
    # On élargit la colonne à VARCHAR(64) AVANT d'ouvrir la transaction de
    # migration (idempotent, AUTOCOMMIT). Compatible PG (no-op si déjà 64+).
    try:
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(64)"
            )
            # Commit immédiat pour que la nouvelle taille soit visible avant
            # le UPDATE alembic_version dans la transaction de migration.
            connection.commit()
    except Exception:
        # Table absente (premier run) ou opération en échec : on ignore.
        # La migration suivante échouera avec un message explicite si nécessaire.
        try:
            connection.rollback()
        except Exception:
            pass

    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Exécuter les migrations en mode async."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Exécuter les migrations en mode 'online' (async)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
