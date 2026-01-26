from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from shared_db import users_table
from routes.auth import User

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role != 'admin':
        flash('Access denied. Admin role required.', 'error')
        return redirect(url_for('index'))

@admin_bp.route('/admin')
def index():
    users = users_table.all()
    # Mask passwords
    for user in users:
        user['password_hash'] = '********'
    return render_template('admin_dashboard.html', users=users)

@admin_bp.route('/admin/users/add', methods=['POST'])
def add_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form.get('role', 'user')
    
    if User.get_by_username(username):
        flash('Username already exists.', 'error')
    else:
        users_table.insert({
            'username': username,
            'password_hash': generate_password_hash(password),
            'role': role
        })
        flash('User added successfully.', 'success')
        
    return redirect(url_for('admin.index'))

@admin_bp.route('/admin/users/delete/<username>', methods=['POST'])
def delete_user(username):
    if username == 'admin':
        flash('Cannot delete default admin.', 'error')
        return redirect(url_for('admin.index'))
        
    if username == current_user.username:
         flash('Cannot delete yourself.', 'error')
         return redirect(url_for('admin.index'))

    from tinydb import Query
    UserQuery = Query()
    users_table.remove(UserQuery.username == username)
    flash(f'User {username} deleted.', 'success')
    return redirect(url_for('admin.index'))
