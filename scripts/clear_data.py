r"""
Clear all rows from applications and candidates tables.
Run from project root: .venv\Scripts\python.exe scripts\clear_data.py
"""
import os, sys
# Ensure project root is on sys.path so imports like `config` and `models` work
proj_root = os.path.dirname(os.path.dirname(__file__))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import Application, Candidate

print('Using DATABASE_URL:', DATABASE_URL)
from sqlalchemy.exc import OperationalError

engine = None
try:
    engine = create_engine(DATABASE_URL, future=True)
    # quick test connect
    with engine.connect() as conn:
        pass
except Exception as e:
    print('Could not connect to configured DATABASE_URL, falling back to SQLite dev.db:', e)
    DATABASE_URL = 'sqlite:///./dev.db'
    engine = create_engine(DATABASE_URL, future=True)
Session = sessionmaker(bind=engine)
s = Session()
try:
    apps_before = s.query(Application).count()
    cands_before = s.query(Candidate).count()
    print(f'Before: applications={apps_before}, candidates={cands_before}')
    s.query(Application).delete()
    s.query(Candidate).delete()
    s.commit()
    apps_after = s.query(Application).count()
    cands_after = s.query(Candidate).count()
    print(f'After: applications={apps_after}, candidates={cands_after}')
except Exception as e:
    s.rollback()
    print('Error clearing data:', e)
finally:
    s.close()
