import os
import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

from models import Base, Admin
from config import DATABASE_URL

def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session()

    email = input('Admin email: ').strip()
    password = getpass.getpass('Password: ')
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    admin = Admin(email=email, password=pw_hash)
    session.add(admin)
    session.commit()
    print('Admin created with id', admin.id)

if __name__ == '__main__':
    main()
