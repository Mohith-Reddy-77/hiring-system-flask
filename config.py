from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret')

UPLOAD_BUCKET = os.getenv('UPLOAD_BUCKET', 'resumes')

# When true, use local filesystem storage for uploads instead of Supabase.
USE_LOCAL_STORAGE = os.getenv('USE_LOCAL_STORAGE', 'false').lower() in ('1', 'true', 'yes')
