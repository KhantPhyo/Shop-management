from flask import Blueprint, request, jsonify
from database import get_db
from auth_utils import check_password, generate_token

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400

    db = get_db()
    try:
        admin = db.execute(
            "SELECT * FROM admins WHERE username = ?", (data['username'],)
        ).fetchone()

        if not admin or not check_password(data['password'], admin['password_hash']):
            return jsonify({'error': 'Invalid credentials'}), 401

        token = generate_token(admin['id'], admin['username'])
        return jsonify({
            'token': token,
            'admin': {'id': admin['id'], 'username': admin['username']}
        })
    finally:
        db.close()
