import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

# ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import DATABASE_URL
from models import Base

config = context.config

if config.config_file_name:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        # Some alembic.ini files may omit logger sections (e.g. logger_sqlalchemy).
        # Ignore logging config errors so migrations can run using defaults.
        pass

target_metadata = Base.metadata


def run_migrations_offline():
    url = DATABASE_URL
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(DATABASE_URL)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
