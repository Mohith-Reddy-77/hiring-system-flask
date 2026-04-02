"""Quick diagnostic: check database and Supabase storage connectivity.

Run: python scripts/check_supabase_connection.py
"""
from dotenv import load_dotenv
load_dotenv()
import os
import sys

# ensure project root is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import DATABASE_URL, SUPABASE_URL, SUPABASE_KEY, UPLOAD_BUCKET, USE_LOCAL_STORAGE

def check_db():
    if not DATABASE_URL:
        print('DATABASE_URL not set')
        return False
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            res = conn.execute(text('SELECT 1'))
            print('DB: OK - SELECT 1 returned', list(res))
        return True
    except Exception as e:
        print('DB: ERROR -', type(e).__name__, str(e))
        return False

def check_supabase_storage():
    try:
        from supabase_client import get_supabase_client
    except Exception as e:
        print('Supabase client import error:', e)
        return False

    client = get_supabase_client()
    # Detect local stub
    if hasattr(client, 'storage') and callable(getattr(client, 'storage', None)):
        print('Supabase: storage is callable (unwrapped by adapter)')
    # Try listing buckets or accessing the configured bucket
    try:
        # adapter exposes list_buckets
        if hasattr(client.storage, 'list_buckets'):
            lb = client.storage.list_buckets()
            print('Supabase: list_buckets() OK ->', type(lb))
        # Try to access bucket
        b = client.storage.from_(UPLOAD_BUCKET)
        # Try a harmless operation depending on API
        if hasattr(b, 'get_public_url'):
            print('Supabase: bucket accessor has get_public_url (local stub)')
        else:
            print('Supabase: bucket accessor type:', type(b))
        return True
    except Exception as e:
        print('Supabase storage error:', type(e).__name__, str(e))
        return False

def main():
    print('DATABASE_URL present:', bool(DATABASE_URL))
    print('SUPABASE_URL present:', bool(SUPABASE_URL))
    print('SUPABASE_KEY present:', bool(SUPABASE_KEY))
    print('USE_LOCAL_STORAGE:', bool(USE_LOCAL_STORAGE))
    print('UPLOAD_BUCKET:', UPLOAD_BUCKET)
    db_ok = check_db()
    supa_ok = check_supabase_storage()
    if db_ok and supa_ok:
        print('\nResult: Supabase and DB appear connected and reachable.')
    elif db_ok:
        print('\nResult: DB OK, Supabase storage not reachable.')
    else:
        print('\nResult: Connectivity issues detected.')

if __name__ == '__main__':
    main()
