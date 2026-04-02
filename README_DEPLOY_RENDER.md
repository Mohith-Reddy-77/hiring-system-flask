Render deployment notes
======================

Quick steps to deploy this Flask app to Render and provision a managed Postgres database.

1) Push your repository to GitHub (or connect your Git provider) so Render can access it.

2) Create a new Web Service on Render:
   - Connect the repo and branch.
   - Environment: `Python`
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn "app:app" --workers 2 --bind 0.0.0.0:$PORT`

3) Provision a managed Postgres on Render:
   - In Render dashboard, create a new Postgres database (starter plan is fine for testing).
   - Attach the DB to your Web Service. Render will automatically provide a `DATABASE_URL` env var to the service.

4) Required environment variables (set in Render service settings):
   - `DATABASE_URL` (if not attached automatically)
   - `JWT_SECRET` (set a secure secret)
   - Optional: `SUPABASE_URL`, `SUPABASE_KEY` (if you use Supabase storage)
       - Optional: `SUPABASE_URL`, `SUPABASE_KEY` (if you use Supabase storage). If you provide these, the app will use Supabase storage for uploaded resumes.
          - For reliable automatic bucket creation on deploy you may need to use a Supabase `service_role` key with storage permissions. If you prefer not to expose a service key in the env, create the bucket manually in the Supabase dashboard and allow anon uploads (or configure RLS policies accordingly).
   - Optional: `UPLOAD_BUCKET` (default: `resumes`)
   - `FLASK_ENV=production`
   - Optional: `FLASK_DEBUG=0`

5) Run migrations (recommended):
   - This repo includes Alembic. After the DB is provisioned, run:

```bash
pip install -r requirements.txt
alembic upgrade head
```

   - If you prefer not to use Alembic, the app will attempt to create missing tables on startup using SQLAlchemy's `create_all()`, but column migrations are best applied via Alembic for Postgres.

6) File uploads/storage:
   - By default the app attempts Supabase storage (if `SUPABASE_URL` and `SUPABASE_KEY` provided).
   - If you prefer local storage on Render, set `USE_LOCAL_STORAGE=true` and ensure the `public/` directory is writable. Note: Render ephemeral filesystem means uploaded files will not persist across deploys — use object storage (Supabase, S3) for persistent uploads.

   Supabase notes:
   - Provide `SUPABASE_URL` and `SUPABASE_KEY` in Render's environment variables to enable Supabase storage.
   - The app will attempt a best-effort creation of the bucket named by `UPLOAD_BUCKET` at startup. If the provided key lacks permissions, create the bucket manually in your Supabase project and make it public or grant upload rights to the anon key.
   - When using Supabase for storage, uploaded files will persist in Supabase storage and are safe across deploys — this is the recommended configuration for production.

   Your project Supabase URL (from your message): `https://esaxwkbpjdzsngrwfaib.supabase.co`

   Important: do NOT paste secret keys into source files or chat. Set `SUPABASE_KEY` in Render's Environment settings to your Supabase `service_role` key (if you want the server to create buckets). If you only have the publishable key (starts with `sb_publishable_...`) you can still use it for uploads only if you configure the bucket and storage policies in the Supabase dashboard to allow anon uploads.

7) Database notes:
   - For production use, run alembic migrations and avoid relying on inline SQLite ALTER TABLE operations.
   - Attach the managed Postgres to the web service so the `DATABASE_URL` connection string is available to your app.

If you'd like, I can:
- Add an Alembic migration script for the `ats_score`/`ats_analysis`/`skills` columns so Postgres is prepared.
- Create a small `.renderignore` or CI step to run migrations automatically after deploy.

Local Supabase test
-------------------

To verify your server can upload to Supabase from your development machine, create a `.env` file in the project root with the following (do NOT commit this file):

```
SUPABASE_URL=https://esaxwkbpjdzsngrwfaib.supabase.co
SUPABASE_KEY=<your_service_role_or_key>
UPLOAD_BUCKET=resumes
```

Then run the test script included in `scripts/test_supabase_upload.py`:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python scripts/test_supabase_upload.py
```

Expected output: the script prints an `upload_res` object and a `public_url` if the bucket is public or the key returns a public URL. If you only provide a publishable key (sb_publishable_...), the script may succeed only if the bucket and policies allow anon uploads.

Running Alembic migrations against Supabase
-----------------------------------------

I added an Alembic migration that creates the project's tables and ensures the storage-related columns: `alembic/versions/0001_create_tables_and_storage.sql.py`.

To run it against your Supabase Postgres (locally or on Render), set `DATABASE_URL` in `.env` (URL-encode the password) and run:

```bash
pip install -r requirements.txt
alembic upgrade head
```

This will create the `admins`, `jobs`, `candidates`, `applications`, and `interviews` tables if they do not already exist.

If you prefer to run raw SQL directly in Supabase, here is the equivalent SQL you can paste into the Supabase SQL editor (copy/paste):

```sql
-- Create admins
CREATE TABLE IF NOT EXISTS admins (
   id serial PRIMARY KEY,
   email varchar(255) UNIQUE NOT NULL,
   password varchar(255) NOT NULL
);

-- Create jobs

Creating the Supabase bucket (helper)
------------------------------------

If you want the app to use Supabase storage for uploads, you need a storage bucket (default name: `resumes`).

1) Preferred: run the helper locally with a `service_role` key in `.env` (do NOT commit `.env`):

```bash
cp .env.example .env
# edit .env and set SUPABASE_URL and SUPABASE_KEY (service_role)
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python scripts/create_supabase_bucket.py
```

2) Alternative: create the bucket manually in the Supabase dashboard `Storage -> Buckets` and set it Public or configure policies so your publishable key can upload.

3) After the bucket exists and is accessible, run the upload test:

```bash
python scripts/test_supabase_upload.py
```

CREATE TABLE IF NOT EXISTS jobs (
   id serial PRIMARY KEY,
   title varchar(255) NOT NULL,
   description text,
   location varchar(255),
   responsibilities jsonb,
   qualifications jsonb,
   created_at timestamptz DEFAULT now()
);

-- Create candidates
CREATE TABLE IF NOT EXISTS candidates (
   id serial PRIMARY KEY,
   name varchar(255),
   email varchar(255) UNIQUE NOT NULL,
   phone varchar(50),
   linkedin varchar(255),
   website varchar(255),
   password varchar(255),
   resumes jsonb,
   skills jsonb,
   created_at timestamptz DEFAULT now()
);

-- Create applications
CREATE TABLE IF NOT EXISTS applications (
   id serial PRIMARY KEY,
   job_id integer REFERENCES jobs(id),
   candidate_id integer REFERENCES candidates(id),
   cover_letter text,
   resume_url varchar(1024),
   ats_score integer DEFAULT 0,
   ats_analysis text,
   status varchar(50) DEFAULT 'Applied',
   created_at timestamptz DEFAULT now()
);

-- Create interviews
CREATE TABLE IF NOT EXISTS interviews (
   id serial PRIMARY KEY,
   application_id integer REFERENCES applications(id),
   scheduled_for timestamptz,
   notes text,
   created_at timestamptz DEFAULT now()
);
```


