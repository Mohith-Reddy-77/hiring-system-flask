"""create initial tables and ensure storage-related columns

Revision ID: 0001_create_tables_and_storage
Revises: 
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_create_tables_and_storage'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Use raw SQL with IF NOT EXISTS to be safe when running against an existing DB
    conn = op.get_bind()

    # Create admins table
    op.execute("""
    CREATE TABLE IF NOT EXISTS admins (
      id serial PRIMARY KEY,
      email varchar(255) UNIQUE NOT NULL,
      password varchar(255) NOT NULL
    );
    """)

    # Create jobs table
    op.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
      id serial PRIMARY KEY,
      title varchar(255) NOT NULL,
      description text,
      location varchar(255),
      responsibilities jsonb,
      qualifications jsonb,
      created_at timestamptz DEFAULT now()
    );
    """)

    # Create candidates table
    op.execute("""
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
    """)

    # Create applications table
    op.execute("""
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
    """)

    # Create interviews table
    op.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
      id serial PRIMARY KEY,
      application_id integer REFERENCES applications(id),
      scheduled_for timestamptz,
      notes text,
      created_at timestamptz DEFAULT now()
    );
    """)


def downgrade():
    # Do not drop tables by default in downgrade to avoid data loss; provide commands commented
    pass
