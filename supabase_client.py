from config import SUPABASE_URL, SUPABASE_KEY, UPLOAD_BUCKET, USE_LOCAL_STORAGE
import os


class _LocalStorageBucket:
    def __init__(self, bucket_name):
        self.bucket = bucket_name
        self.base_dir = os.path.join(os.getcwd(), 'public', bucket_name)
        os.makedirs(self.base_dir, exist_ok=True)

    def upload(self, filename, data):
        path = os.path.join(self.base_dir, filename)
        # data may be bytes
        mode = 'wb'
        with open(path, mode) as f:
            f.write(data)
        return {'data': {'Key': filename}, 'error': None}

    def get_public_url(self, filename):
        # Serve from /public/<bucket>/<filename>
        public_path = f"/public/{self.bucket}/{filename}"
        return {'publicURL': public_path}


class _LocalSupabaseLike:
    def __init__(self):
        self._buckets = {}

    def storage(self):
        return self

    def from_(self, bucket_name):
        if bucket_name not in self._buckets:
            self._buckets[bucket_name] = _LocalStorageBucket(bucket_name)
        return self._buckets[bucket_name]


def get_supabase_client():
    # If the developer explicitly requests local storage, use the filesystem stub.
    if USE_LOCAL_STORAGE:
        return _LocalSupabaseLike()
    # Lazy import so tests that don't exercise Supabase don't require the package
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client
        except Exception as e:
            raise RuntimeError('supabase package is required to use Supabase client') from e

        raw_client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Provide a small adapter so callers can use `client.storage.from_(...)`
        # regardless of whether the upstream `storage` attribute is a callable
        # or an object (different supabase-py versions differ here).
        class _StorageAccessor:
            def __init__(self, client):
                self._client = client

            def _get_storage(self):
                st = getattr(self._client, 'storage', None)
                # Some versions of supabase client expose `storage` as a callable
                # that returns another callable or object. Unwrap callables up to
                # a small depth to reach the actual storage object.
                depth = 0
                while callable(st) and depth < 4:
                    try:
                        st = st()
                    except Exception:
                        # If calling fails, break and return what we have.
                        break
                    depth += 1
                return st

            def __getattr__(self, name):
                storage = self._get_storage()
                if storage is None:
                    raise AttributeError('underlying client has no storage')
                attr = getattr(storage, name)
                return attr

            # convenience helpers that some code calls on the top-level storage
            def from_(self, bucket_name):
                storage = self._get_storage()
                return storage.from_(bucket_name)

            def create_bucket(self, *args, **kwargs):
                storage = self._get_storage()
                return storage.create_bucket(*args, **kwargs)

            def list_buckets(self, *args, **kwargs):
                storage = self._get_storage()
                return storage.list_buckets(*args, **kwargs)

        class _ClientAdapter:
            def __init__(self, raw):
                self._raw = raw
                # expose storage accessor as attribute for compatibility
                self.storage = _StorageAccessor(raw)

            def __getattr__(self, name):
                return getattr(self._raw, name)

        client = _ClientAdapter(raw_client)

        # Try to ensure the upload bucket exists. This may require a service_role
        # key depending on your Supabase project's storage policies. We swallow
        # errors here so deployments still succeed when the key lacks permissions.
        try:
            try:
                client.storage.create_bucket(UPLOAD_BUCKET, public=True)
            except Exception:
                try:
                    buckets = client.storage.list_buckets()
                except Exception:
                    pass
        except Exception:
            pass

        return client

    # Fallback to local filesystem-based stub for development if credentials missing.
    return _LocalSupabaseLike()
