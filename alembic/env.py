"""
alembic/env.py
──────────────
Alembic environment.  Wires our SQLAlchemy Base + sync URL so that
`alembic revision --autogenerate` can discover all ORM models.
"""

from logging.config import fileConfig
import sys, os

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── make sure the project root is on sys.path ────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings                 # noqa: E402
from app.db.models import Base                  # noqa: E402  – pulls in all models

# ── standard Alembic config ──────────────────────────────────────────
config = context.config
if config.file_config:
    fileConfig(config.file_config)

target_metadata = Base.metadata


def run_migrations_offline():
    url = settings.postgres.sync_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": settings.postgres.sync_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
