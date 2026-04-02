# Hiring System (Flask + Supabase)

Minimal hiring management backend implemented with Flask and Supabase (Postgres + Storage).

Quick start

1. Copy `.env.example` to `.env` and fill in values (SUPABASE_URL, SUPABASE_KEY, DATABASE_URL, JWT_SECRET).
2. Create a Python virtualenv and install dependencies:

```bash
python -m venv .venv
.venv\\Scripts\\activate    # Windows
pip install -r requirements.txt
```

3. Initialize DB tables (the app uses SQLAlchemy `create_all` on startup for dev).
4. Run the app:

```bash
set FLASK_APP=app.py
set FLASK_ENV=development
flask run
```

Notes
- This is a minimal scaffold. For production: run migrations, secure JWT, and configure deploy (Render/Heroku/Railway) and Supabase buckets.

Migrations and moving to Supabase/Postgres

- To use Alembic for migrations (recommended):
	- Install dependencies: `pip install -r requirements.txt`
	- Initialize and create a revision: `alembic revision --autogenerate -m "init"`
	- Apply migrations: `alembic upgrade head`

- To test against a local Postgres instance, use `docker-compose up -d` (this creates Postgres on `localhost:5432`).

- To migrate data from a local SQLite DB to Postgres, set environment variables and run the included script:

```bash
set SOURCE_DATABASE_URL=sqlite:///./dev.db
set TARGET_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hiring
python migrate_sqlite_to_postgres.py
```

