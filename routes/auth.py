from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from tinydb import Query
from shared_db import users_table
import os
import time
import uuid
from urllib.parse import urlsplit

_attempts = {}

auth_bp = Blueprint('auth', __name__)

class User(UserMixin):
    def __init__(self, doc_id, username, password_hash, role='user', department='Chưa có PK', display_name=None):
        self.id = str(doc_id)
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.department = department
        self.display_name = display_name if display_name else username

    @staticmethod
    def get(user_id):
        try:
            user_data = users_table.get(doc_id=int(user_id))
        except (ValueError, TypeError):
            return None
        if user_data and (user_data.get('disabled') or session.get('auth_version', '0') != user_data.get('auth_version', '0')):
            return None
        if user_data and not user_data.get('disabled'):
            return User(
                doc_id=user_data.doc_id,
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                role=user_data.get('role', 'user'),
                department=user_data.get('department', 'Nhi'),
                display_name=user_data.get('display_name')
            )
        return None

    @staticmethod
    def get_by_username(username):
        UserQuery = Query()
        user_data = users_table.get(UserQuery.username == username)
        if user_data and not user_data.get('disabled'):
             return User(
                doc_id=user_data.doc_id,
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                role=user_data.get('role', 'user'),
                department=user_data.get('department', 'Chưa có PK'),
                display_name=user_data.get('display_name')
            )
        return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    if request.method == 'POST':
        username = request.form.get('username', '')[:200]
        password = request.form.get('password', '')
        now = time.monotonic()
        for key in list(_attempts):
            if now - _attempts[key][0] >= 900:
                del _attempts[key]
        attempt_key = request.remote_addr or 'unknown'
        if _attempts.get(attempt_key, (now, 0))[1] >= 10:
            abort(429, description='Quá nhiều lần đăng nhập sai. Thử lại sau 15 phút.')
        
        user = User.get_by_username(username)
        
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            login_user(user)
            stored = users_table.get(doc_id=int(user.id))
            session['auth_version'] = stored.get('auth_version', '0')
            session.permanent = True
            session['last_activity'] = time.time()
            session['authenticated_at'] = time.time()
            session['must_change_password'] = stored.get('must_change_password', False) or len(password) < 12
            _attempts.pop(attempt_key, None)
            flash('Logged in successfully.', 'success')
            if session['must_change_password']:
                return redirect(url_for('auth.change_password'))
            next_page = request.args.get('next', '')
            parsed = urlsplit(next_page)
            if parsed.scheme or parsed.netloc or not next_page.startswith('/') or next_page.startswith('//') or '\\' in next_page:
                next_page = ''
            return redirect(next_page or url_for('core.index'))
        else:
            first, count = _attempts.get(attempt_key, (now, 0))
            _attempts[attempt_key] = (first, count + 1)
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# Keep setup_default_admin separate or call it from app.py
def setup_default_admin():
    if not users_table.all():
        password = os.getenv('QKB_BOOTSTRAP_PASSWORD', '')
        if len(password) < 12:
            raise RuntimeError('For first setup, set QKB_BOOTSTRAP_PASSWORD to at least 12 characters. No default password is created.')
        users_table.insert({
            'username': 'admin',
            'password_hash': generate_password_hash(password),
            'role': 'admin',
            'department': 'Chưa có PK',
            'display_name': 'Admin',
            'must_change_password': True,
        })
        print('Bootstrap administrator created. Change its password after first login.')


@auth_bp.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        password = request.form.get('new_password', '')
        if not check_password_hash(current_user.password_hash, current):
            abort(400, description='Mật khẩu hiện tại không đúng.')
        if len(password) < 12 or password != request.form.get('confirm_password') or password == current:
            abort(400, description='Mật khẩu mới cần ít nhất 12 ký tự, khác mật khẩu cũ và xác nhận trùng khớp.')
        version = uuid.uuid4().hex
        users_table.update({'password_hash': generate_password_hash(password), 'auth_version': version,
                            'must_change_password': False}, doc_ids=[int(current_user.id)])
        session['auth_version'] = version
        session['must_change_password'] = False
        flash('Đã đổi mật khẩu và thu hồi các phiên đăng nhập khác.', 'success')
        return redirect(url_for('core.index'))
    return render_template('change_password.html')
