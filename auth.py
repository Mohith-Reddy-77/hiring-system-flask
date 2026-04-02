from functools import wraps
from flask import request, redirect
import jwt
from config import JWT_SECRET

def generate_token(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token: str) -> dict:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return data
    except Exception:
        return None

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect('/admin/login')
        data = verify_token(token)
        if not data:
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated


def admin_api_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return ({'message': 'Unauthorized'}, 401)
        data = verify_token(token)
        if not data:
            return ({'message': 'Unauthorized'}, 401)
        return f(*args, **kwargs)
    return decorated


def candidate_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('candidate_token')
        if not token:
            return redirect('/candidate/login')
        data = verify_token(token)
        if not data:
            return redirect('/candidate/login')
        return f(*args, **kwargs)
    return decorated


def get_candidate_from_token():
    token = request.cookies.get('candidate_token')
    if not token:
        return None
    return verify_token(token)
