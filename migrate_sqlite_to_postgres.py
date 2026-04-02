"""Simple data migration helper: reads from current SQLite (DATABASE_URL) and copies rows to target Postgres URL.
Usage:
  Set env: SOURCE_DATABASE_URL (e.g. sqlite:///./dev.db) and TARGET_DATABASE_URL (postgres://...)
  Run: python migrate_sqlite_to_postgres.py
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Job, Candidate, Application, Interview, Base


def copy_table(session_src, session_dst, model, transform=None):
    items = session_src.query(model).all()
    for it in items:
        data = {c.name: getattr(it, c.name) for c in model.__table__.columns if c.name != 'id'}
        if transform:
            data = transform(data)
        new = model(**data)
        session_dst.add(new)
    session_dst.commit()


def main():
    src_url = os.environ.get('SOURCE_DATABASE_URL')
    tgt_url = os.environ.get('TARGET_DATABASE_URL')
    if not src_url or not tgt_url:
        print('Set SOURCE_DATABASE_URL and TARGET_DATABASE_URL in environment')
        return

    src_engine = create_engine(src_url)
    tgt_engine = create_engine(tgt_url)
    SessionSrc = sessionmaker(bind=src_engine)
    SessionTgt = sessionmaker(bind=tgt_engine)

    # ensure target schema exists
    Base.metadata.create_all(bind=tgt_engine)

    ssrc = SessionSrc()
    stgt = SessionTgt()

    copy_table(ssrc, stgt, Job)
    copy_table(ssrc, stgt, Candidate)
    copy_table(ssrc, stgt, Application)
    copy_table(ssrc, stgt, Interview)

    print('Migration complete')


if __name__ == '__main__':
    main()
