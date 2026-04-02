from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt
import os
from models import Base, Admin
from config import DATABASE_URL
def create_admin(email, password):
    dburl = DATABASE_URL if DATABASE_URL else 'sqlite:///./dev.db'
    # If configured DATABASE_URL fails, fall back to local sqlite.
    try:
        engine = create_engine(dburl, future=True)
        Session = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print('Warning: cannot connect using DATABASE_URL, falling back to sqlite. Error:', e)
        dburl = 'sqlite:///./dev.db'
        engine = create_engine(dburl, future=True)
        Session = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)
    session = Session()
    existing = session.query(Admin).filter_by(email=email).first()
    if existing:
        print('Admin already exists with id', existing.id)
        return
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    admin = Admin(email=email, password=pw_hash)
    session.add(admin)
    session.commit()
    print('Created admin id=', admin.id)

if __name__ == '__main__':
    create_admin('admin@example.com', 'adminpass')
