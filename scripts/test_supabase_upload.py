"""Simple test script to verify Supabase storage uploads from this project.

Usage:
  - Create a `.env` file or set env vars: `SUPABASE_URL`, `SUPABASE_KEY`, optionally `UPLOAD_BUCKET`.
  - Run: `python scripts/test_supabase_upload.py`

The script will attempt to upload a small text file to the configured bucket
and print the upload response and public URL (if available).
"""
from dotenv import load_dotenv
load_dotenv()
import os
import sys
import time

# Ensure project root is on sys.path so imports like `supabase_client` work when
# running this script directly from the `scripts/` folder.
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from supabase_client import get_supabase_client
from config import UPLOAD_BUCKET


def main():
    bucket = UPLOAD_BUCKET or os.getenv('UPLOAD_BUCKET') or 'resumes'
    client = get_supabase_client()

    filename = f"test-upload-{int(time.time())}.txt"
    data = b"Supabase upload test from local script\n"

    # Try several ways to access the bucket depending on supabase-py version
    def diagnose_storage(obj):
        try:
            print('storage repr:', repr(obj))
            print('storage type:', type(obj))
            print('storage dir snapshot:', [n for n in dir(obj) if not n.startswith('_')][:50])
        except Exception as e:
            print('diagnose_storage failed:', e)

    storage_obj = getattr(client, 'storage', None)
    diagnose_storage(storage_obj)

    storage = None
    errors = []

    # Pattern 1: client.storage.from_(bucket)
    try:
        storage = client.storage.from_(bucket)
        print('Using pattern: client.storage.from_(bucket)')
    except Exception as e:
        errors.append(('from_', str(e)))

    # Pattern 2: client.storage() or client.storage(bucket)
    if storage is None:
        try:
            if callable(storage_obj):
                # Some implementations expose storage as a method that takes no
                # args and returns an accessor object. Try calling without
                # arguments first.
                try:
                    maybe = storage_obj()
                    # if this returns something useful, prefer it
                    if maybe is not None:
                        storage = maybe
                        print('Using pattern: client.storage()')
                except TypeError:
                    # If calling without args fails, try with bucket arg
                    maybe = storage_obj(bucket)
                    storage = maybe
                    print('Using pattern: client.storage(bucket)')
        except Exception as e:
            errors.append(('call_storage', str(e)))

    # Pattern 3: client.storage.fromBucket(bucket) or client.storage.fromBucket
    if storage is None:
        try:
            if hasattr(storage_obj, 'fromBucket'):
                storage = storage_obj.fromBucket(bucket)
                print('Using pattern: storage.fromBucket(bucket)')
        except Exception as e:
            errors.append(('fromBucket', str(e)))

    # Pattern 4: client.storage.upload(bucket, filename, data) direct
    direct_upload_support = False
    if storage is None:
        try:
            if hasattr(storage_obj, 'upload') and callable(storage_obj.upload):
                direct_upload_support = True
                print('Using pattern: client.storage.upload(bucket, filename, data)')
        except Exception as e:
            errors.append(('direct_upload_check', str(e)))

    if storage is None and not direct_upload_support:
        print('Could not resolve storage bucket. Patterns tried and errors:')
        for p, e in errors:
            print('-', p, e)
        return

    # If we got a storage accessor object (like the local stub) that exposes
    # `from_` to return a real bucket, and it doesn't itself have `upload`,
    # call `.from_(bucket)` to get the actual bucket object.
    try:
        if storage is not None and not hasattr(storage, 'upload') and hasattr(storage, 'from_'):
            storage = storage.from_(bucket)
            print('Resolved storage via storage.from_(bucket)')
    except Exception as e:
        print('Resolving storage.from_(bucket) failed:', e)

    # Try the common upload signatures, fall back to writing a temp file
    upload_res = None
    try:
        # Most code paths in this project call upload(filename, data)
        if direct_upload_support:
            upload_res = storage_obj.upload(bucket, filename, data)
        else:
            upload_res = storage.upload(filename, data)
    except TypeError:
        # Some client versions expect a file path. Write temp file and retry.
        tmp_path = os.path.join(os.getcwd(), filename)
        with open(tmp_path, 'wb') as f:
            f.write(data)
        try:
            try:
                if direct_upload_support:
                    upload_res = storage_obj.upload(bucket, filename)
                else:
                    upload_res = storage.upload(filename, tmp_path)
            except Exception as e:
                print('upload with file path failed:', e)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        print('Upload attempt failed:', e)

    print('upload_res:', upload_res)

    # Try to get a public URL
    try:
        if direct_upload_support:
            # Try a few places to get a public URL when direct upload API is used
            try:
                url_res = client.storage.get_public_url(filename)
            except Exception:
                try:
                    url_res = client.storage.from_(bucket).get_public_url(filename)
                except Exception as e:
                    print('get_public_url failed:', e)
                    url_res = None
        else:
            url_res = None
            try:
                url_res = storage.get_public_url(filename)
            except Exception:
                try:
                    url_res = client.storage.get_public_url(filename)
                except Exception as e:
                    print('get_public_url failed:', e)

        if url_res is not None:
            try:
                public_url = url_res.get('publicURL') or url_res.get('publicUrl') or url_res.get('public_url')
            except Exception:
                public_url = str(url_res)
            print('public_url:', public_url)
    except Exception as e:
        print('get_public_url failed:', e)


if __name__ == '__main__':
    main()
