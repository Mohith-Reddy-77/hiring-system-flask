import os
import importlib
import json

def setup_module(module):
    # Use an on-disk sqlite DB for tests to avoid needing Postgres
    os.environ['DATABASE_URL'] = 'sqlite:///test_app.db'
    os.environ['SUPABASE_URL'] = 'http://localhost'
    os.environ['SUPABASE_KEY'] = 'test-key'


def test_health_and_jobs_endpoint(tmp_path):
    # Import app after env setup by loading file directly (avoid module path issues)
    import importlib.util
    from pathlib import Path
    app_path = Path(__file__).resolve().parents[1] / 'app.py'
    # Ensure project root is on sys.path so local imports in app.py work
    import sys
    sys.path.insert(0, str(app_path.parent))
    spec = importlib.util.spec_from_file_location('app_mod', str(app_path))
    app_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_mod)
    app = app_mod.app
    client = app.test_client()

    r = client.get('/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'ok'

    # Create a job via POST
    job_payload = {
        'title': 'Test Engineer',
        'description': 'Testing job',
        'location': 'Remote'
    }
    r = client.post('/jobs', json=job_payload)
    assert r.status_code == 201
    job_data = r.get_json()
    assert 'id' in job_data

    # GET jobs
    r = client.get('/jobs')
    assert r.status_code == 200
    jobs = r.get_json()
    assert any(j['title'] == 'Test Engineer' for j in jobs)
