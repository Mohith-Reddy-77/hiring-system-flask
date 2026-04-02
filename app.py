from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_from_directory
import pathlib
from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import json

from config import DATABASE_URL, JWT_SECRET, UPLOAD_BUCKET, USE_LOCAL_STORAGE
import sys
from auth import generate_token, admin_required, verify_token
import bcrypt
from models import Admin
from auth import candidate_required, get_candidate_from_token
from models import Base, Job, Candidate, Application, Interview
from supabase_client import get_supabase_client
from ats import calculate_ats_score, extract_skills
import io
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

app = Flask(__name__)

# Database setup
# Allow a developer-friendly default when running `python app.py` directly.
# The project prefers an explicit `DATABASE_URL` (e.g. for Postgres/Supabase).
# If no `DATABASE_URL` is provided, fall back to a local SQLite DB for quick dev runs.
if not DATABASE_URL:
    dev_db = 'sqlite:///./dev.db'
    print('WARNING: DATABASE_URL not set, falling back to development SQLite:', dev_db)
    DATABASE_URL = dev_db

# Track whether a DATABASE_URL was provided by the environment (vs. dev fallback)
_USER_PROVIDED_DB = bool(os.getenv('DATABASE_URL'))

from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect, text


# Try to use the configured DATABASE_URL, but fall back to a local SQLite file
# if the configured database is unreachable or misconfigured.
def _create_engine_and_session(db_url):
    engine = create_engine(db_url, future=True)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


try:
    engine, SessionLocal = _create_engine_and_session(DATABASE_URL)
    # Create tables that do not exist
    Base.metadata.create_all(bind=engine)
    # Ensure ats_score column exists on applications table (add for sqlite if missing)
    try:
        insp = inspect(engine)
        cols = [c['name'] for c in insp.get_columns('applications')] if 'applications' in insp.get_table_names() else []
        # check candidates table columns too
        cand_cols = [c['name'] for c in insp.get_columns('candidates')] if 'candidates' in insp.get_table_names() else []
        # Ensure applications table has ats_score and optionally ats_analysis; and candidates has skills
        if ('ats_score' not in cols) or ('ats_analysis' not in cols) or ('skills' not in cand_cols):
            if engine.dialect.name == 'sqlite':
                with engine.connect() as conn:
                    if 'ats_score' not in cols:
                        try:
                            conn.execute(text('ALTER TABLE applications ADD COLUMN ats_score INTEGER DEFAULT 0'))
                        except Exception:
                            pass
                    if 'ats_analysis' not in cols:
                        try:
                            conn.execute(text("ALTER TABLE applications ADD COLUMN ats_analysis TEXT"))
                        except Exception:
                            pass
                    if 'skills' not in cand_cols:
                        try:
                            conn.execute(text("ALTER TABLE candidates ADD COLUMN skills TEXT"))
                        except Exception:
                            pass
                    conn.commit()
                print('Applied inline sqlite ALTER TABLE to add missing columns (ats_score/ats_analysis/skills)')
            else:
                print('Database is missing expected columns; please run migrations for your DB')
    except Exception:
        pass
except Exception as exc:
    # If the user explicitly provided DATABASE_URL but connection failed, fail fast
    if _USER_PROVIDED_DB:
        print('ERROR: could not connect to configured DATABASE_URL. Aborting startup. Error:', exc)
        sys.exit(1)
    # Otherwise we are in a dev environment without DATABASE_URL; fall back to SQLite
    print('Warning: could not connect to DATABASE_URL; falling back to local SQLite. Error:', exc)
    DATABASE_URL = 'sqlite:///./dev.db'
    engine, SessionLocal = _create_engine_and_session(DATABASE_URL)
    Base.metadata.create_all(bind=engine)


def ensure_candidates_skills_column():
    try:
        insp = inspect(engine)
        if 'candidates' in insp.get_table_names():
            cand_cols = [c['name'] for c in insp.get_columns('candidates')]
            if 'skills' not in cand_cols and engine.dialect.name == 'sqlite':
                with engine.connect() as conn:
                    try:
                        conn.execute(text("ALTER TABLE candidates ADD COLUMN skills TEXT"))
                    except Exception:
                        pass
                    conn.commit()
                print('Applied inline sqlite ALTER TABLE to add missing column: candidates.skills')
    except Exception as e:
        try:
            print('ensure_candidates_skills_column error:', e)
        except Exception:
            pass

# run once at startup to reduce chance of OperationalError on candidate lookups
ensure_candidates_skills_column()


def ensure_applications_columns():
    try:
        insp = inspect(engine)
        if 'applications' in insp.get_table_names():
            cols = [c['name'] for c in insp.get_columns('applications')]
            if engine.dialect.name == 'sqlite':
                with engine.connect() as conn:
                    if 'ats_score' not in cols:
                        try:
                            conn.execute(text('ALTER TABLE applications ADD COLUMN ats_score INTEGER DEFAULT 0'))
                        except Exception:
                            pass
                    if 'ats_analysis' not in cols:
                        try:
                            conn.execute(text("ALTER TABLE applications ADD COLUMN ats_analysis TEXT"))
                        except Exception:
                            pass
                    conn.commit()
                print('Applied inline sqlite ALTER TABLE to add missing columns on applications (ats_score/ats_analysis)')
    except Exception as e:
        try:
            print('ensure_applications_columns error:', e)
        except Exception:
            pass

ensure_applications_columns()


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/debug/db')
def debug_db():
    try:
        url = str(engine.url)
        # mask password if present
        import re
        url_masked = re.sub(r':([^:@]+)@', ':***@', url)
        dialect = engine.dialect.name
        return jsonify({'database_url': url_masked, 'dialect': dialect})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/jobs', methods=['GET', 'POST'])
def jobs():
    session = SessionLocal()
    if request.method == 'GET':
        q = request.args.get('q', '').strip()
        if q:
            jobs = session.query(Job).filter(Job.title.ilike(f"%{q}%")).all()
        else:
            jobs = session.query(Job).all()
        out = []
        for j in jobs:
            out.append({'id': j.id, 'title': j.title, 'description': j.description, 'location': j.location})
        # Render template for browser GET
        if request.accept_mimetypes.best == 'text/html' or request.headers.get('Accept', '').find('text/html') != -1:
            return render_template('jobs.html', jobs=out, query=q)
        return jsonify(out)

    data = request.json or {}
    job = Job(
        title=data.get('title'),
        description=data.get('description'),
        location=data.get('location'),
        responsibilities=json.dumps(data.get('responsibilities') or []),
        qualifications=json.dumps(data.get('qualifications') or []),
    )
    session.add(job)
    session.commit()
    return jsonify({'id': job.id}), 201


@app.route('/jobs/<int:job_id>', methods=['GET', 'PUT', 'DELETE'])
def job_detail(job_id):
    session = SessionLocal()
    job = session.get(Job, job_id)
    if not job:
        return jsonify({'error': 'not found'}), 404
    if request.method == 'GET':
        data = {'id': job.id, 'title': job.title, 'description': job.description, 'location': job.location}
        if request.accept_mimetypes.best == 'text/html' or request.headers.get('Accept', '').find('text/html') != -1:
            return render_template('job_detail.html', job=data)
        return jsonify(data)
    if request.method == 'PUT':
        data = request.json or {}
        for k, v in data.items():
            if hasattr(job, k):
                setattr(job, k, v)
        session.commit()
        return jsonify({'id': job.id})
    if request.method == 'DELETE':
        session.delete(job)
        session.commit()
        return '', 204


@app.route('/applications', methods=['GET', 'POST'])
def applications():
    session = SessionLocal()
    if request.method == 'GET':
        apps = session.query(Application).all()
        return jsonify([{'id': a.id, 'job_id': a.job_id, 'candidate_id': a.candidate_id, 'status': a.status} for a in apps])

    # POST - form-data expected with resume file
    form = request.form
    name = form.get('name')
    email = form.get('email')
    phone = form.get('phone')
    cover_letter = form.get('coverLetter')
    job_id = form.get('jobId')

    # Find candidate - do NOT auto-create here. Require explicit registration.
    candidate = session.query(Candidate).filter_by(email=email).first()
    if not candidate:
        msg = 'Candidate does not exist. Please register before applying.'
        # If browser form, render registration page with message
        if request.accept_mimetypes.best == 'text/html' or request.headers.get('Accept', '').find('text/html') != -1:
            return render_template('candidate_register.html', error=msg), 400
        return jsonify({'message': msg}), 400

    # Extract resume text either from a posted textarea or from uploaded PDF
    resume_text = request.form.get('resumeText', '')

    filename = None
    if 'resume' in request.files and request.files['resume'].filename:
        resume = request.files['resume']
        filename = f"{int(__import__('time').time())}-{resume.filename}"
        data = resume.read()

        # Try to extract text from PDF if PyPDF2 is available and file looks like PDF
        text_extracted = ''
        if PyPDF2 and resume.filename.lower().endswith('.pdf'):
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(data))
                pages = []
                for p in reader.pages:
                    try:
                        pages.append(p.extract_text() or '')
                    except Exception:
                        pages.append('')
                text_extracted = '\n'.join(pages)
            except Exception as e:
                current_app.logger.info('PDF text extraction failed: %s', e)

        # Fallback: if no extracted text, try to decode any textual bytes from the file
        if not resume_text and not text_extracted:
            try:
                decoded = data.decode('utf-8', errors='ignore')
                # Keep printable characters and newlines
                import re as _re
                cleaned = _re.sub(r'[^\x09\x0A\x0D\x20-\x7E]', ' ', decoded)
                # Collapse whitespace
                cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
                if len(cleaned) > 20:
                    text_extracted = cleaned
            except Exception:
                pass

        if not resume_text and text_extracted:
            resume_text = text_extracted

        current_app.logger.info('Resume extraction: filename=%s, extracted_len=%d, resumeText_provided=%s', resume.filename, len(resume_text or ''), bool(request.form.get('resumeText')))

        # upload to storage (Supabase or local fallback)
        supabase = get_supabase_client()
        public_url = None
        try:
            res = supabase.storage.from_(UPLOAD_BUCKET).upload(filename, data)
            if isinstance(res, dict) and res.get('error'):
                raise RuntimeError(f"Supabase upload error: {res}")
            try:
                res = supabase.storage.from_(UPLOAD_BUCKET).get_public_url(filename)
                # supabase-py may return different key names; accept both forms.
                public_url = res.get('publicURL') or res.get('publicUrl') or None
            except Exception:
                public_url = None
        except Exception as e:
            current_app.logger.warning('Supabase upload failed: %s', e)
            try:
                public_dir = os.path.join(os.getcwd(), 'public', UPLOAD_BUCKET)
                os.makedirs(public_dir, exist_ok=True)
                path = os.path.join(public_dir, filename)
                with open(path, 'wb') as f:
                    f.write(data)
                public_url = f"/public/{UPLOAD_BUCKET}/{filename}"
            except Exception as e2:
                current_app.logger.error('Local fallback upload failed: %s', e2)
                return jsonify({'message': 'Upload failed'}), 500
    else:
        public_url = None

    # Compute ATS score and analysis from resume_text if available, and extract skills
    try:
        ats_score = 0
        ats_analysis = None
        if resume_text and len(resume_text) >= 30:
            ats_score, ats_analysis = calculate_ats_score(resume_text)
            try:
                skills = extract_skills(resume_text)
            except Exception:
                skills = []
            # persist skills onto candidate record
            try:
                candidate.skills = skills
                session.add(candidate)
                session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass
        else:
            ats_score = 0
            ats_analysis = None
    except Exception as e:
        current_app.logger.warning('ATS scoring failed: %s', e)
        ats_score = 0
        ats_analysis = None

    application = Application(
        job_id=int(job_id),
        candidate_id=candidate.id,
        cover_letter=cover_letter,
        resume_url=public_url,
        ats_score=ats_score,
        ats_analysis=ats_analysis,
        status='Applied'
    )
    session.add(application)
    try:
        session.commit()
    except OperationalError as oe:
        # session may be in a failed state; rollback first
        try:
            session.rollback()
        except Exception:
            pass
        msg = str(oe).lower()
        if ('no column named ats_score' in msg or 'has no column named ats_score' in msg or 'no such column: ats_score' in msg) or ('no column named ats_analysis' in msg or 'has no column named ats_analysis' in msg or 'no such column: ats_analysis' in msg):
            # Try to add column and retry once (sqlite)
            try:
                if engine.dialect.name == 'sqlite':
                    with engine.connect() as conn:
                        try:
                            conn.execute(text('ALTER TABLE applications ADD COLUMN ats_score INTEGER DEFAULT 0'))
                        except Exception:
                            pass
                        try:
                            conn.execute(text("ALTER TABLE applications ADD COLUMN ats_analysis TEXT"))
                        except Exception:
                            pass
                        conn.commit()
                    current_app.logger.info('Added ats_score/ats_analysis columns to applications table, retrying insert in a fresh session')
                    # Retry insert in a new session to avoid PendingRollbackError
                    NewSession = sessionmaker(bind=engine)
                    new_s = NewSession()
                    new_app = Application(
                        job_id=application.job_id,
                        candidate_id=application.candidate_id,
                        cover_letter=application.cover_letter,
                        resume_url=application.resume_url,
                        ats_score=getattr(application, 'ats_score', 0),
                        ats_analysis=getattr(application, 'ats_analysis', None),
                        status=application.status
                    )
                    new_s.add(new_app)
                    new_s.commit()
                    # replace application reference with the newly committed one
                    application = new_app
                else:
                    raise
            except Exception as e:
                current_app.logger.error('Failed to add ats_score column and retry insert: %s', e)
                raise
        else:
            raise

    # If this was a browser form submission, redirect to a friendly success page.
    if request.accept_mimetypes.best == 'text/html' or request.headers.get('Accept', '').find('text/html') != -1:
        return redirect(url_for('application_success', job_id=job_id))

    return jsonify({'id': application.id, 'resume_url': public_url}), 201


# Admin job CRUD (protected)
@app.route('/admin/jobs')
@admin_required
def admin_jobs():
    session = SessionLocal()
    jobs = session.query(Job).all()
    out = [{'id': j.id, 'title': j.title, 'description': j.description, 'location': j.location} for j in jobs]
    return render_template('admin_jobs.html', jobs=out)


@app.route('/admin/candidates')
@admin_required
def admin_candidates():
    session = SessionLocal()
    candidates = session.query(Candidate).order_by(Candidate.created_at.desc()).all()
    return render_template('admin_candidates.html', candidates=candidates)


@app.route('/admin/applications')
@admin_required
def admin_applications():
    session = SessionLocal()
    apps = session.query(Application).order_by(Application.created_at.desc()).all()
    out = []
    for a in apps:
        cand = session.get(Candidate, a.candidate_id)
        job = session.get(Job, a.job_id)
        out.append({'id': a.id, 'candidate_name': cand.name if cand else 'Unknown', 'candidate_email': cand.email if cand else '', 'job_title': job.title if job else 'Unknown', 'status': a.status, 'created_at': a.created_at, 'resume_url': a.resume_url, 'cover_letter': a.cover_letter, 'ats_score': getattr(a, 'ats_score', 0)})
    return render_template('admin_applications.html', applications=out)


@app.route('/admin/applications/<int:app_id>')
@admin_required
def admin_application_detail(app_id):
    session = SessionLocal()
    a = session.get(Application, app_id)
    if not a:
        return 'Not found', 404
    cand = session.get(Candidate, a.candidate_id)
    job = session.get(Job, a.job_id)
    app_obj = {'id': a.id, 'candidate_name': cand.name if cand else 'Unknown', 'candidate_email': cand.email if cand else '', 'job_title': job.title if job else 'Unknown', 'status': a.status, 'resume_url': a.resume_url, 'cover_letter': a.cover_letter, 'ats_score': getattr(a, 'ats_score', 0), 'ats_analysis': getattr(a, 'ats_analysis', None), 'candidate_skills': getattr(cand, 'skills', None)}
    # If this is requested as a fragment for the admin shell, return the fragment
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('fragment') == '1':
        return render_template('admin_application_detail_fragment.html', app=app_obj)
    return render_template('admin_application_detail.html', app=app_obj)


@app.route('/admin/interviews')
@admin_required
def admin_interviews():
    session = SessionLocal()
    interviews = session.query(Interview).order_by(Interview.scheduled_for.desc()).all()
    out = []
    for it in interviews:
        app_rec = session.get(Application, it.application_id)
        cand = session.get(Candidate, app_rec.candidate_id) if app_rec else None
        job = session.get(Job, app_rec.job_id) if app_rec else None
        out.append({'candidate_name': cand.name if cand else 'Unknown', 'job_title': job.title if job else 'Unknown', 'scheduled_for': it.scheduled_for, 'notes': it.notes})
    return render_template('admin_interviews.html', interviews=out)


@app.route('/admin/interviews/schedule', methods=['POST'])
@admin_required
def schedule_interview():
    session = SessionLocal()
    application_id = int(request.form.get('application_id'))
    scheduled_for = request.form.get('scheduled_for')
    notes = request.form.get('notes')
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(scheduled_for)
    except Exception:
        return 'Invalid datetime format; use ISO format e.g. 2026-04-03T15:00:00', 400
    interview = Interview(application_id=application_id, scheduled_for=dt, notes=notes)
    session.add(interview)
    session.commit()
    return redirect('/admin/interviews')


@app.route('/admin/jobs/new', methods=['GET', 'POST'])
@admin_required
def admin_jobs_new():
    session = SessionLocal()
    if request.method == 'GET':
        return render_template('admin_job_form.html', job=None, action='/admin/jobs/new')
    data = request.form
    job = Job(title=data.get('title'), description=data.get('description'), location=data.get('location'))
    session.add(job)
    session.commit()
    return redirect('/admin/jobs')


@app.route('/admin/clear-data', methods=['GET', 'POST'])
@admin_required
def admin_clear_data():
    session = SessionLocal()
    if request.method == 'GET':
        return render_template('admin_clear_data.html')
    # POST: delete applications first, then candidates
    try:
        session.query(Application).delete()
        session.query(Candidate).delete()
        session.commit()
        flash('All candidates and applications deleted.', 'success')
    except Exception as e:
        session.rollback()
        current_app.logger.error('Failed to clear data: %s', e)
        flash('Failed to delete data: ' + str(e), 'danger')
    return redirect('/admin/jobs')


@app.route('/admin/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_jobs_edit(job_id):
    session = SessionLocal()
    job = session.get(Job, job_id)
    if not job:
        return 'Not found', 404
    if request.method == 'GET':
        return render_template('admin_job_form.html', job=job, action=f'/admin/jobs/{job_id}/edit')
    data = request.form
    job.title = data.get('title')
    job.location = data.get('location')
    job.description = data.get('description')
    session.commit()
    return redirect('/admin/jobs')


@app.route('/admin/jobs/<int:job_id>/delete', methods=['POST'])
@admin_required
def admin_jobs_delete(job_id):
    session = SessionLocal()
    job = session.get(Job, job_id)
    if job:
        session.delete(job)
        session.commit()
    return redirect('/admin/jobs')


# Candidate auth + dashboard
@app.route('/candidate/register', methods=['GET', 'POST'])
def candidate_register():
    session = SessionLocal()
    if request.method == 'GET':
        return render_template('candidate_register.html')
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    if session.query(Candidate).filter_by(email=email).first():
        return render_template('candidate_register.html', error='Email already registered')
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    candidate = Candidate(name=name, email=email, password=pw_hash, resumes=[])
    session.add(candidate)
    session.commit()
    token = generate_token({'id': candidate.id, 'email': candidate.email})
    resp = redirect('/candidate/dashboard')
    resp.set_cookie('candidate_token', token, httponly=True, secure=(os.getenv('FLASK_ENV') == 'production'))
    return resp


@app.route('/candidate/login', methods=['GET', 'POST'])
def candidate_login():
    session = SessionLocal()
    if request.method == 'GET':
        return render_template('candidate_login.html')
    # Simplified candidate access: only email required. If candidate does not exist, create a record.
    email = request.form.get('email')
    if not email:
        return render_template('candidate_login.html', error='Email is required')
    candidate = session.query(Candidate).filter_by(email=email).first()
    if not candidate:
        # Do not auto-create candidate on login. Require explicit registration first.
        return render_template('candidate_login.html', error='Candidate not found. Please register first.'), 400
    token = generate_token({'id': candidate.id, 'email': candidate.email})
    resp = redirect('/candidate/dashboard')
    resp.set_cookie('candidate_token', token, httponly=True, secure=(os.getenv('FLASK_ENV') == 'production'))
    return resp


@app.route('/candidate/logout')
def candidate_logout():
    resp = redirect('/')
    resp.set_cookie('candidate_token', '', expires=0)
    return resp


@app.route('/candidate/dashboard')
@candidate_required
def candidate_dashboard():
    session = SessionLocal()
    tok = get_candidate_from_token()
    if not tok:
        return redirect('/candidate/login')
    candidate = session.get(Candidate, tok.get('id'))
    apps = session.query(Application).filter_by(candidate_id=candidate.id).all()
    apps_out = []
    for a in apps:
        job = session.get(Job, a.job_id)
        apps_out.append({'id': a.id, 'job_id': a.job_id, 'job_title': job.title if job else 'Unknown', 'status': a.status, 'created_at': a.created_at, 'ats_score': getattr(a, 'ats_score', 0), 'resume_url': a.resume_url})
    return render_template('candidate_dashboard.html', candidate=candidate, applications=apps_out)


@app.route('/applications/success')
def application_success():
    job_id = request.args.get('job_id')
    return render_template('application_success.html', job_id=job_id)


@app.route('/admin/analyze', methods=['POST'])
def analyze():
    data = request.json or {}
    resume_text = data.get('resumeText', '')
    if not resume_text or len(resume_text) < 50:
        return jsonify({'success': True, 'score': 0, 'analysis': 'Resume text too short or missing.'})
    score, analysis = calculate_ats_score(resume_text)
    return jsonify({'success': True, 'score': score, 'analysis': analysis})


@app.route('/')
def index():
    # Redirect to jobs listing
    return jobs()


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Render the admin shell which will load content dynamically
    return render_template('admin_base.html')


# Content endpoints return fragments loaded into the admin shell via AJAX
@app.route('/admin/content/dashboard')
@admin_required
def admin_content_dashboard():
    session = SessionLocal()
    stats = {
        'jobs': session.query(Job).count(),
        'candidates': session.query(Candidate).count(),
        'applications': session.query(Application).count(),
        'interviews': session.query(Interview).count(),
    }
    recent_apps = session.query(Application).order_by(Application.created_at.desc()).limit(8).all()
    recent_activity = []
    for a in recent_apps:
        cand = session.get(Candidate, a.candidate_id)
        job = session.get(Job, a.job_id)
        recent_activity.append({'title': job.title if job else 'Unknown', 'name': cand.name if cand else 'Unknown', 'createdAt': a.created_at})
    return render_template('admin_dashboard_fragment.html', stats=stats, recent_activity=recent_activity)


@app.route('/admin/content/candidates')
@admin_required
def admin_content_candidates():
    session = SessionLocal()
    candidates = session.query(Candidate).order_by(Candidate.created_at.desc()).all()
    return render_template('admin_candidates_fragment.html', candidates=candidates)


@app.route('/admin/content/applications')
@admin_required
def admin_content_applications():
    session = SessionLocal()
    # Filters: job_id, min_score, max_score, status, q (candidate name/email)
    q_param = request.args.get('q', '').strip()
    job_id = request.args.get('job_id')
    try:
        min_score = int(request.args.get('min_score')) if request.args.get('min_score') else None
    except Exception:
        min_score = None
    try:
        max_score = int(request.args.get('max_score')) if request.args.get('max_score') else None
    except Exception:
        max_score = None
    status = request.args.get('status')
    page = int(request.args.get('page') or 1)
    per_page = int(request.args.get('per_page') or 25)

    query = session.query(Application)
    if job_id:
        try:
            query = query.filter(Application.job_id == int(job_id))
        except Exception:
            pass
    if min_score is not None:
        query = query.filter(Application.ats_score >= min_score)
    if max_score is not None:
        query = query.filter(Application.ats_score <= max_score)
    if status:
        query = query.filter(Application.status == status)
    if q_param:
        # join Candidate and filter on name or email
        from sqlalchemy.orm import joinedload
        query = query.join(Candidate).filter((Candidate.name.ilike(f"%{q_param}%")) | (Candidate.email.ilike(f"%{q_param}%")))

    query = query.order_by(Application.created_at.desc())
    total = query.count()
    apps = query.offset((page - 1) * per_page).limit(per_page).all()
    out = []
    for a in apps:
        cand = session.get(Candidate, a.candidate_id)
        job = session.get(Job, a.job_id)
        out.append({'id': a.id, 'candidate_name': cand.name if cand else 'Unknown', 'job_title': job.title if job else 'Unknown', 'status': a.status, 'created_at': a.created_at, 'ats_score': getattr(a, 'ats_score', 0)})
    # pass pagination info to fragment
    pagination = {'page': page, 'per_page': per_page, 'total': total}
    return render_template('admin_applications_fragment.html', applications=out, pagination=pagination, filters={'q': q_param, 'job_id': job_id, 'min_score': min_score, 'max_score': max_score, 'status': status})


@app.route('/admin/content/interviews')
@admin_required
def admin_content_interviews():
    session = SessionLocal()
    interviews = session.query(Interview).order_by(Interview.scheduled_for.desc()).all()
    out = []
    for it in interviews:
        app_rec = session.get(Application, it.application_id)
        cand = session.get(Candidate, app_rec.candidate_id) if app_rec else None
        job = session.get(Job, app_rec.job_id) if app_rec else None
        out.append({'candidate_name': cand.name if cand else 'Unknown', 'job_title': job.title if job else 'Unknown', 'scheduled_for': it.scheduled_for, 'notes': it.notes})
    return render_template('admin_interviews_fragment.html', interviews=out)


@app.route('/admin/content/jobs')
@admin_required
def admin_content_jobs():
    session = SessionLocal()
    jobs = session.query(Job).order_by(Job.created_at.desc()).all()
    out = [{'id': j.id, 'title': j.title, 'location': j.location} for j in jobs]
    return render_template('admin_jobs_fragment.html', jobs=out)


@app.route('/admin/content/application/<int:app_id>')
@admin_required
def admin_content_application(app_id):
    session = SessionLocal()
    a = session.get(Application, app_id)
    if not a:
        return ('Not found', 404)
    cand = session.get(Candidate, a.candidate_id)
    job = session.get(Job, a.job_id)
    app_obj = {'id': a.id, 'candidate_name': cand.name if cand else 'Unknown', 'candidate_email': cand.email if cand else '', 'job_title': job.title if job else 'Unknown', 'status': a.status, 'resume_url': a.resume_url, 'cover_letter': a.cover_letter, 'ats_score': getattr(a, 'ats_score', 0), 'ats_analysis': getattr(a, 'ats_analysis', None), 'candidate_skills': getattr(cand, 'skills', None)}
    return render_template('admin_application_detail_fragment.html', app=app_obj)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')

    email = request.form.get('email')
    password = request.form.get('password')
    session = SessionLocal()
    admin = session.query(Admin).filter_by(email=email).first()
    if not admin:
        return render_template('admin_login.html', error='Invalid credentials')

    # Validate stored password. Some legacy records may store plaintext or
    # malformed hashes which cause `bcrypt.checkpw` to raise ValueError("Invalid salt").
    pw_ok = False
    try:
        if admin.password:
            pw_ok = bcrypt.checkpw(password.encode('utf-8'), admin.password.encode('utf-8'))
    except ValueError:
        # Stored password is not a valid bcrypt salt/hash. As a compatibility
        # measure, accept a plaintext match and re-hash it into bcrypt for
        # future logins.
        try:
            if password == admin.password:
                # re-hash and persist
                new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                admin.password = new_hash
                session.add(admin)
                session.commit()
                pw_ok = True
        except Exception:
            pw_ok = False

    if not pw_ok:
        return render_template('admin_login.html', error='Invalid credentials')

    token = generate_token({'id': admin.id, 'email': admin.email})
    resp = redirect('/admin/dashboard')
    resp.set_cookie('token', token, httponly=True, secure=(os.getenv('FLASK_ENV') == 'production'))
    return resp


@app.route('/admin/logout')
def admin_logout():
    resp = redirect('/admin/login')
    resp.set_cookie('token', '', expires=0)
    return resp


@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    token = request.cookies.get('token')
    data = verify_token(token)
    if not data:
        return redirect('/admin/login')
    admin_id = data.get('id')
    session = SessionLocal()
    admin = session.get(Admin, admin_id)
    if not admin:
        return redirect('/admin/login')

    if request.method == 'GET':
        return render_template('admin_change_password.html')

    current = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if not new or new != confirm:
        from flask import flash
        flash('New passwords do not match', 'error')
        return render_template('admin_change_password.html')

    # verify current password (handle legacy plaintext stored password)
    valid = False
    try:
        if admin.password:
            valid = bcrypt.checkpw(current.encode('utf-8'), admin.password.encode('utf-8'))
    except ValueError:
        # legacy plaintext
        if current == admin.password:
            valid = True

    if not valid:
        from flask import flash
        flash('Current password is incorrect', 'error')
        return render_template('admin_change_password.html')

    # update password
    try:
        new_hash = bcrypt.hashpw(new.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin.password = new_hash
        session.add(admin)
        session.commit()
        from flask import flash
        flash('Password changed successfully', 'success')
        return redirect('/admin/dashboard')
    except Exception as e:
        from flask import flash
        flash('Failed to change password', 'error')
        return render_template('admin_change_password.html')


@app.route('/public/<path:filename>')
def public_files(filename):
    # Serve files from the project's `public` directory (resumes, static uploads)
    public_dir = pathlib.Path(os.getcwd()) / 'public'
    return send_from_directory(str(public_dir), filename)


if __name__ == '__main__':
    # Only enable Flask's debug mode when not running in production.
    debug_mode = os.getenv('FLASK_ENV', '').lower() != 'production' and os.getenv('FLASK_DEBUG', '') != '0'
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=debug_mode)
