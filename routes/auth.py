from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from tinydb import Query
from shared_db import users_table

auth_bp = Blueprint('auth', __name__)

class User(UserMixin):
    def __init__(self, doc_id, username, password_hash, role='user'):
        self.id = str(doc_id)
        self.username = username
        self.password_hash = password_hash
        self.role = role

    @staticmethod
    def get(user_id):
        user_data = users_table.get(doc_id=int(user_id))
        if user_data:
            return User(
                doc_id=user_data.doc_id,
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                role=user_data.get('role', 'user')
            )
        return None

    @staticmethod
    def get_by_username(username):
        UserQuery = Query()
        user_data = users_table.get(UserQuery.username == username)
        if user_data:
             return User(
                doc_id=user_data.doc_id,
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                role=user_data.get('role', 'user')
            )
        return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.get_by_username(username)
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# Keep setup_default_admin separate or call it from app.py
def setup_default_admin():
    if not users_table.all():
        print("Creating default admin user...")
        # Hardcoded default for initial setup only
        default_password = 'admin' 
        users_table.insert({
            'username': 'admin',
            'password_hash': generate_password_hash(default_password),
            'role': 'admin'
        })
        print(f"Default admin created. Username: admin, Password: {default_password}")
