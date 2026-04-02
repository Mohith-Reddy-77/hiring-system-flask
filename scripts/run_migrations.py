"""Run Alembic migrations against the database specified in .env (DATABASE_URL).

Usage:
  - Ensure `.env` contains `DATABASE_URL` pointing to your Supabase Postgres (URL-encode password).
  - Run: `python scripts/run_migrations.py`

This will execute `alembic upgrade head` programmatically.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import sys

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from alembic.config import Config
from alembic import command
from config import DATABASE_URL

def main():
    if not DATABASE_URL:
        print('DATABASE_URL not set. Please set it in .env or environment.')
        sys.exit(1)

    # Use the local alembic.ini
    alembic_cfg = Config(os.path.join(ROOT, 'alembic.ini'))
    # Override sqlalchemy.url from env
    try:
        alembic_cfg.set_main_option('sqlalchemy.url', DATABASE_URL)
    except Exception:
        pass

    print('Running alembic upgrade head against:', DATABASE_URL)
    command.upgrade(alembic_cfg, 'head')


if __name__ == '__main__':
    main()
