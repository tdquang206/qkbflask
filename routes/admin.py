from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from shared_db import users_table
from routes.auth import User
from routes.settings import load_settings
from utils.storage import export_decrypted_databases, get_json_database_files
import os
import io

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
        
    settings = load_settings()
    departments = settings.get('departments', ["PK Nhi", "PK Da liễu"])
    return render_template('admin_dashboard.html', users=users, departments=departments)

@admin_bp.route('/admin/users/add', methods=['POST'])
def add_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form.get('role', 'user')
    department = request.form.get('department', 'Chưa có PK')
    display_name = request.form.get('display_name', username)
    
    if User.get_by_username(username):
        flash('Username already exists.', 'error')
    else:
        users_table.insert({
            'username': username,
            'password_hash': generate_password_hash(password),
            'role': role,
            'department': department,
            'display_name': display_name
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

@admin_bp.route('/admin/users/edit/<username>', methods=['POST'])
def edit_user(username):
    role = request.form.get('role')
    department = request.form.get('department')
    display_name = request.form.get('display_name')
    
    if not role or not department or not display_name:
        flash('Missing required fields.', 'error')
        return redirect(url_for('admin.index'))

    from tinydb import Query
    UserQuery = Query()
    
    # We update by username
    users_table.update({
        'role': role,
        'department': department,
        'display_name': display_name
    }, UserQuery.username == username)
    
    flash(f'User {username} updated.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/admin/database/decrypt')
def decrypt_database_page():
    """Display the decrypt/export database page"""
    # Get list of JSON files available for export
    json_files = get_json_database_files()
    
    # Check if there are any exported files
    export_dir = 'decrypted_exports'
    exported_files = []
    if os.path.exists(export_dir):
        for filename in os.listdir(export_dir):
            if filename.startswith('decrypted_') and filename.endswith('.json'):
                filepath = os.path.join(export_dir, filename)
                if os.path.isfile(filepath):
                    exported_files.append({
                        'filename': filename,
                        'size': os.path.getsize(filepath),
                        'original_filename': filename.replace('decrypted_', '')
                    })
    
    exported_files.sort(key=lambda x: x['filename'])
    
    return render_template('admin_decrypt.html', 
                         json_files=[name for name, _ in json_files],
                         exported_files=exported_files,
                         export_dir=export_dir)


@admin_bp.route('/admin/database/export', methods=['POST'])
def export_databases():
    """Decrypt and export all database files"""
    try:
        result = export_decrypted_databases()
        
        if result['success']:
            success_msg = f"Successfully exported {len(result['success'])} file(s): {', '.join([f['filename'] for f in result['success']])}"
            flash(success_msg, 'success')
        
        if result['errors']:
            error_msg = f"Errors during export: {'; '.join([f'{f[0]}: {f[1]}' for f in result['errors']])}"
            flash(error_msg, 'warning')
        
        return redirect(url_for('admin.decrypt_database_page'))
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('admin.decrypt_database_page'))


@admin_bp.route('/admin/database/download/<filename>')
def download_decrypted_file(filename):
    """Download a decrypted database file"""
    # Validate filename to prevent directory traversal
    if '/' in filename or '\\' in filename or '..' in filename:
        flash('Invalid filename', 'error')
        return redirect(url_for('admin.decrypt_database_page'))
    
    if not filename.startswith('decrypted_'):
        flash('Invalid file', 'error')
        return redirect(url_for('admin.decrypt_database_page'))
    
    export_dir = 'decrypted_exports'
    filepath = os.path.join(export_dir, filename)
    
    if not os.path.exists(filepath):
        flash('File not found', 'error')
        return redirect(url_for('admin.decrypt_database_page'))
    
    try:
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
    except Exception as e:
        flash(f'Download failed: {str(e)}', 'error')
        return redirect(url_for('admin.decrypt_database_page'))


@admin_bp.route('/admin/database/import-page')
def import_database_page():
    """Placeholder for import database page"""
    return render_template('admin_import.html')


@admin_bp.route('/admin/database/import', methods=['POST'])
def import_database():
    """Placeholder for importing database functionality"""
    flash('Import functionality is coming soon!', 'info')
    return redirect(url_for('admin.import_database_page'))


@admin_bp.route('/admin/edit-exam-info', methods=['GET', 'POST'])
def edit_exam_info():
    """Admin tool to search and edit exam info (doctor, department)"""
    from shared_db import patients_table as Patients_db
    from tinydb import Query
    exam_found = None
    patient_found = None
    all_doctors = set()
    settings = load_settings()
    departments = settings.get('departments', [])
    
    # Collect all doctors from exams to display as dropdown options
    for patient in Patients_db.all():
        for exam in patient.get('exams', []):
            doctor = exam.get('created_by_name', '')
            if doctor:
                all_doctors.add(doctor)
    all_doctors = sorted(list(all_doctors))
    
    if request.method == 'POST':
        action = request.form.get('action')
        print(f"[DEBUG] Action: {action}")
        
        if action == 'search':
            search_exam_id = request.form.get('exam_id', '').strip()
            print(f"[DEBUG] Searching for exam_id: {search_exam_id}")
            
            # Search for exam in all patients
            for patient in Patients_db.all():
                for exam in patient.get('exams', []):
                    if exam.get('id') == search_exam_id:
                        exam_found = exam
                        patient_found = patient
                        print(f"[DEBUG] Found exam: {exam_found}")
                        break
                if exam_found:
                    break
            
            if not exam_found:
                flash(f'Exam ID "{search_exam_id}" not found', 'error')
                print(f"[DEBUG] Exam not found for ID: {search_exam_id}")
        
        elif action == 'save':
            # Get the exam_id from the form
            exam_id = request.form.get('edit_exam_id', '').strip()
            new_doctor = request.form.get('doctor_name', '').strip()
            new_department = request.form.get('department', '').strip()
            
            print(f"[DEBUG] Save action: exam_id={exam_id}, doctor={new_doctor}, dept={new_department}")
            
            # Validate inputs
            if not new_doctor:
                flash('Doctor name cannot be empty', 'error')
                return redirect(url_for('admin.edit_exam_info'))
            
            if not new_department:
                flash('Department cannot be empty', 'error')
                return redirect(url_for('admin.edit_exam_info'))
            
            # Re-search for the exam using exam_id from form
            for patient in Patients_db.all():
                for exam in patient.get('exams', []):
                    if exam.get('id') == exam_id:
                        patient_found = patient
                        exam_found = exam
                        break
                if exam_found:
                    break
            
            if not exam_found or not patient_found:
                flash(f'Exam ID "{exam_id}" not found in database', 'error')
                print(f"[DEBUG] Could not re-find exam for save: {exam_id}")
                return redirect(url_for('admin.edit_exam_info'))
            
            # Update the exam in the patient record
            exams = patient_found.get('exams', [])
            updated = False
            for i, exam in enumerate(exams):
                if exam.get('id') == exam_id:
                    print(f"[DEBUG] Found exam at index {i}, updating...")
                    # Update only doctor and department
                    exams[i]['created_by_name'] = new_doctor
                    exams[i]['department'] = new_department
                    updated = True
                    print(f"[DEBUG] Updated exam data: {exams[i]}")
                    break
            
            if updated:
                # Save back to database
                try:
                    print(f"[DEBUG] Saving to database with doc_id: {patient_found.doc_id}")
                    Patients_db.update({'exams': exams}, doc_ids=[patient_found.doc_id])
                    print(f"[DEBUG] Successfully saved!")
                    flash(f'✅ Toa thuốc {exam_id} đã cập nhật thành công!', 'success')
                    # Redirect to clear the form and show success message
                    return redirect(url_for('admin.edit_exam_info'))
                except Exception as e:
                    print(f"[DEBUG] Error saving: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    flash(f'❌ Lỗi khi lưu: {str(e)}', 'error')
                    return redirect(url_for('admin.edit_exam_info'))
            else:
                flash('❌ Không tìm thấy toa thuốc để cập nhật', 'error')
                print(f"[DEBUG] Exam ID mismatch")
                return redirect(url_for('admin.edit_exam_info'))
    
    return render_template('edit_exam_info.html', 
                         exam=exam_found, 
                         patient=patient_found,
                         doctors=all_doctors, 
                         departments=departments)
