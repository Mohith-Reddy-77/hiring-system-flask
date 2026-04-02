import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Job

# Config fallback — match the app's behavior so running this script locally works.
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    DATABASE_URL = 'sqlite:///./dev.db'

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine)


def load_seed(path='seeds/jobs_seed.json'):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_jobs():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    data = load_seed()
    inserted = 0
    for item in data:
        title = item.get('title')
        # avoid duplicates by title
        exists = session.query(Job).filter_by(title=title).first()
        if exists:
            continue
        job = Job(
            title=title,
            description=item.get('description'),
            location=item.get('location'),
            responsibilities=item.get('responsibilities') or [],
            qualifications=item.get('qualifications') or []
        )
        session.add(job)
        inserted += 1
    session.commit()
    session.close()
    print(f"Seed complete — inserted {inserted} new jobs.")


if __name__ == '__main__':
    seed_jobs()
