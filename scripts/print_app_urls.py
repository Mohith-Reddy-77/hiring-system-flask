from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import Application
import os, sys
proj_root = os.path.dirname(os.path.dirname(__file__))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)
print('Using DATABASE_URL:', DATABASE_URL)
engine = create_engine(DATABASE_URL, future=True)
Session = sessionmaker(bind=engine)
s = Session()
apps = s.query(Application).all()
for a in apps:
    print('ID:', a.id, 'resume_url:', a.resume_url)
print('Total apps:', len(apps))
s.close()
