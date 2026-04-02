"""Create or verify the Supabase storage bucket referenced by UPLOAD_BUCKET.

Usage:
  - Place your SUPABASE_URL and SUPABASE_KEY (service_role) in a local .env file.
  - Run: `python scripts/create_supabase_bucket.py`

This is a convenience helper; it performs a best-effort bucket creation and reports status.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import sys

# Ensure project root is on sys.path so imports from top-level modules work
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import SUPABASE_URL, SUPABASE_KEY, UPLOAD_BUCKET

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print('SUPABASE_URL and SUPABASE_KEY must be set in your environment or .env file')
        sys.exit(1)

    try:
        from supabase import create_client
    except Exception as e:
        print('supabase package is required. Install with: pip install supabase')
        raise

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    bucket = UPLOAD_BUCKET or os.getenv('UPLOAD_BUCKET') or 'resumes'
    print(f'Checking bucket: {bucket}')

    try:
        # Try to create bucket as public; if it already exists this may raise an error.
        res = client.storage.create_bucket(bucket, public=True)
        print('create_bucket response:', res)
    except Exception as e:
        print('create_bucket failed (might already exist or insufficient permissions):', e)
        try:
            buckets = client.storage.list_buckets()
            names = [b['name'] for b in buckets]
            print('Available buckets:', names)
            if bucket in names:
                print('Bucket exists.')
            else:
                print('Bucket not found in list; check permissions or create via Supabase dashboard.')
        except Exception as e2:
            print('Failed to list buckets:', e2)

    # Try to get a public URL for a non-existent file to check permissions
    try:
        test_url = client.storage.from_(bucket).get_public_url('nonexistent.txt')
        print('get_public_url result sample:', test_url)
    except Exception as e:
        print('get_public_url failed:', e)

    print('Done')


if __name__ == '__main__':
    main()
