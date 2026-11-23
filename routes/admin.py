from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from tinydb import Query
from shared_db import users_table
from routes.auth import User
from routes.settings import load_settings
from utils.storage import export_decrypted_databases, get_json_database_files
import os
import io
import re
import json
import difflib
import shutil
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role != 'admin':
        flash('Access denied. Admin role required.', 'error')
        abort(403)
    if request.endpoint == 'admin.edit_exam_info' and request.method == 'POST' and request.form.get('action') == 'save':
        # Legacy tool can rewrite authorship and bypass owner-only clinical edits.
        abort(403, description='Không được thay đổi bác sĩ tạo hồ sơ. Sửa nội dung trong lần khám của chính bác sĩ.')
    if request.endpoint in ('admin.export_databases', 'admin.download_decrypted_file') and os.getenv('QKB_ALLOW_PLAINTEXT_EXPORTS') != '1':
        abort(403, description='Xuất dữ liệu giải mã đang tắt. Dùng bản sao lưu mã hóa trong mục Sao lưu đầy đủ.')

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
    if role not in ('admin', 'doctor', 'receptionist', 'cashier', 'pharmacist', 'user') or len(password) < 12:
        abort(400, description='Vai trò không hợp lệ hoặc mật khẩu ngắn hơn 12 ký tự.')
    
    if users_table.get(Query().username == username):
        flash('Username already exists.', 'error')
    else:
        users_table.insert({
            'username': username,
            'password_hash': generate_password_hash(password),
            'role': role,
            'department': department,
            'display_name': display_name,
            'must_change_password': True,
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
    users_table.update({'disabled': True, 'auth_version': uuid.uuid4().hex}, UserQuery.username == username)
    flash(f'User {username} disabled. Exam ownership is preserved.', 'success')
    return redirect(url_for('admin.index'))

@admin_bp.route('/admin/users/edit/<username>', methods=['POST'])
def edit_user(username):
    role = request.form.get('role')
    department = request.form.get('department')
    display_name = request.form.get('display_name')
    if role not in ('admin', 'doctor', 'receptionist', 'cashier', 'pharmacist', 'user'):
        abort(400)
    if username == current_user.username and role != 'admin':
        abort(400, description='Không được tự bỏ quyền quản trị viên.')
    
    if not role or not department or not display_name:
        flash('Missing required fields.', 'error')
        return redirect(url_for('admin.index'))

    from tinydb import Query
    UserQuery = Query()
    
    # We update by username
    users_table.update({
        'role': role,
        'department': department,
        'display_name': display_name,
        'auth_version': uuid.uuid4().hex
    }, UserQuery.username == username)
    
    flash(f'User {username} updated.', 'success')
    return redirect(url_for('admin.index'))


@admin_bp.route('/admin/users/reset/<username>', methods=['POST'])
def reset_user_password(username):
    from tinydb import Query
    if not check_password_hash(current_user.password_hash, request.form.get('admin_password', '')):
        abort(403, description='Cần xác nhận mật khẩu quản trị viên.')
    password = request.form.get('new_password', '')
    if len(password) < 12:
        abort(400, description='Mật khẩu tạm cần ít nhất 12 ký tự.')
    if not users_table.get(Query().username == username):
        abort(404)
    users_table.update({'password_hash': generate_password_hash(password), 'must_change_password': True,
                        'auth_version': uuid.uuid4().hex}, Query().username == username)
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
    # Strict allowlist keeps names deterministic and blocks traversal payloads.
    if not re.fullmatch(r'decrypted_[A-Za-z0-9._-]+\.json', filename):
        flash('Invalid file', 'error')
        return redirect(url_for('admin.decrypt_database_page'))

    export_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'decrypted_exports'))
    filepath = os.path.realpath(os.path.join(export_dir, filename))

    if os.path.commonpath([export_dir, filepath]) != export_dir:
        flash('Invalid file path', 'error')
        return redirect(url_for('admin.decrypt_database_page'))

    if not os.path.exists(filepath):
        flash('File not found', 'error')
        return redirect(url_for('admin.decrypt_database_page'))

    try:
        return send_from_directory(
            export_dir,
            filename,
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
        
        if action == 'search':
            search_exam_id = request.form.get('exam_id', '').strip()
            
            # Search for exam in all patients
            for patient in Patients_db.all():
                for exam in patient.get('exams', []):
                    if exam.get('id') == search_exam_id:
                        exam_found = exam
                        patient_found = patient
                        break
                if exam_found:
                    break
            
            if not exam_found:
                flash(f'Exam ID "{search_exam_id}" not found', 'error')
        
        elif action == 'save':
            # Get the exam_id from the form
            exam_id = request.form.get('edit_exam_id', '').strip()
            new_doctor = request.form.get('doctor_name', '').strip()
            new_department = request.form.get('department', '').strip()
            
            
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
                return redirect(url_for('admin.edit_exam_info'))
            
            # Update the exam in the patient record
            exams = patient_found.get('exams', [])
            updated = False
            for i, exam in enumerate(exams):
                if exam.get('id') == exam_id:
                    # Update only doctor and department
                    exams[i]['created_by_name'] = new_doctor
                    exams[i]['department'] = new_department
                    updated = True
                    break
            
            if updated:
                # Save back to database
                try:
                    Patients_db.update({'exams': exams}, doc_ids=[patient_found.doc_id])
                    flash(f'✅ Toa thuốc {exam_id} đã cập nhật thành công!', 'success')
                    # Redirect to clear the form and show success message
                    return redirect(url_for('admin.edit_exam_info'))
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    flash(f'❌ Lỗi khi lưu: {str(e)}', 'error')
                    return redirect(url_for('admin.edit_exam_info'))
            else:
                flash('❌ Không tìm thấy toa thuốc để cập nhật', 'error')
                return redirect(url_for('admin.edit_exam_info'))
    
    return render_template('edit_exam_info.html', 
                         exam=exam_found, 
                         patient=patient_found,
                         doctors=all_doctors, 
                         departments=departments)


# ─────────────────────────────────────────────────────────────────────────────
# Checkpoint Restore
# ─────────────────────────────────────────────────────────────────────────────

_ADM_ROOT = os.path.abspath(os.getcwd())
_ADM_CP_DIR = os.path.abspath(os.path.join(_ADM_ROOT, 'backups', 'checkpoints'))
_ADM_BACKUP_DIR = os.path.abspath(os.path.join(_ADM_ROOT, 'backups'))
_ADM_DB_FILES = ['db.json', 'db_services.json', 'money_log.json', 'db_mua_thuoc.json']
_DB_BASE_TO_LIVE = {
    'db': 'db.json',
    'db_services': 'db_services.json',
    'money_log': 'money_log.json',
    'db_mua_thuoc': 'db_mua_thuoc.json',
}
_CP_FNAME_RE = re.compile(
    r'^(.+)_(\d{8}_\d{6})_(db\.json|db_services\.json|money_log\.json|db_mua_thuoc\.json)$'
)
_SAFE_TAG_RE = re.compile(r'^[\w][\w\-]{0,80}$')
_SAFE_TS_RE = re.compile(r'^\d{8}_\d{6}$')
_WEEKLY_BACKUP_RE = re.compile(r'^(db|db_services|money_log|db_mua_thuoc)_backup_(\d{4}_\d{2})\.json$')
_WEEK_ID_RE = re.compile(r'^\d{4}_\d{2}$')
_SAFE_FILENAME_RE = re.compile(r'^[A-Za-z0-9._-]+\.json$')


def _format_timestamp(ts_text):
    if not ts_text or len(ts_text) != 15:
        return ts_text
    return f"{ts_text[0:4]}-{ts_text[4:6]}-{ts_text[6:8]} {ts_text[9:11]}:{ts_text[11:13]}:{ts_text[13:15]}"


def _infer_live_db_from_backup_name(fname):
    for base, live_db in _DB_BASE_TO_LIVE.items():
        if fname.startswith(base + '_') or fname == (base + '.json'):
            return live_db
    return None


def _read_db_snapshot(path):
    from utils.storage import decrypt_file

    # Newer backups are encrypted; old migration backups may be plaintext JSON.
    try:
        return decrypt_file(path)
    except Exception:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)


def _write_live_db_snapshot(path, data):
    from utils.storage import EncryptedJSONStorage

    storage = EncryptedJSONStorage(path)
    storage.write(data)
    storage.close()


def _list_checkpoint_groups():
    if not os.path.exists(_ADM_CP_DIR):
        return []
    groups = {}
    for fname in os.listdir(_ADM_CP_DIR):
        m = _CP_FNAME_RE.match(fname)
        if not m:
            continue
        tag, ts, db_file = m.group(1), m.group(2), m.group(3)
        key = f"{tag}||{ts}"
        if key not in groups:
            groups[key] = {
                'source': 'checkpoint',
                'kind_label': 'Checkpoint',
                'group_key': key,
                'tag': tag,
                'timestamp': ts,
                'display_time': _format_timestamp(ts),
                'files': [],
                'key': key,
                'sort_key': ts,
            }
        fpath = os.path.join(_ADM_CP_DIR, fname)
        groups[key]['files'].append({
            'db_file': db_file,
            'filename': fname,
            'size': os.path.getsize(fpath),
        })
    return sorted(groups.values(), key=lambda x: x.get('sort_key', ''), reverse=True)


def _list_regular_backup_groups():
    if not os.path.exists(_ADM_BACKUP_DIR):
        return []

    weekly_groups = {}
    legacy_groups = []

    for fname in os.listdir(_ADM_BACKUP_DIR):
        fpath = os.path.join(_ADM_BACKUP_DIR, fname)
        if not os.path.isfile(fpath) or not fname.endswith('.json'):
            continue

        weekly_match = _WEEKLY_BACKUP_RE.match(fname)
        if weekly_match:
            base, week_id = weekly_match.group(1), weekly_match.group(2)
            group_key = week_id
            if group_key not in weekly_groups:
                weekly_groups[group_key] = {
                    'source': 'weekly_backup',
                    'kind_label': 'Weekly Backup',
                    'group_key': group_key,
                    'tag': f'week_{week_id}',
                    'timestamp': week_id,
                    'display_time': f'Week {week_id}',
                    'files': [],
                    'sort_key': week_id,
                }
            weekly_groups[group_key]['files'].append({
                'db_file': _DB_BASE_TO_LIVE.get(base, base + '.json'),
                'filename': fname,
                'size': os.path.getsize(fpath),
            })
            continue

        # Include old non-weekly snapshots (for example pre-uuid migration files).
        inferred_live = _infer_live_db_from_backup_name(fname)
        if inferred_live:
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            legacy_groups.append({
                'source': 'legacy_backup',
                'kind_label': 'Legacy Backup',
                'group_key': fname,
                'tag': fname,
                'timestamp': mtime.strftime('%Y%m%d_%H%M%S'),
                'display_time': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                'files': [{
                    'db_file': inferred_live,
                    'filename': fname,
                    'size': os.path.getsize(fpath),
                }],
                'sort_key': mtime.strftime('%Y%m%d_%H%M%S'),
            })

    combined = list(weekly_groups.values()) + legacy_groups
    return sorted(combined, key=lambda x: x.get('sort_key', ''), reverse=True)


def _list_restore_groups():
    combined = _list_checkpoint_groups() + _list_regular_backup_groups()
    return sorted(combined, key=lambda x: x.get('sort_key', ''), reverse=True)


def _resolve_snapshot_files(source, group_key):
    snapshot_files = []

    if source == 'checkpoint':
        parts = str(group_key or '').split('||')
        if len(parts) != 2:
            return []
        tag, ts = parts[0], parts[1]
        if not _SAFE_TAG_RE.match(tag) or not _SAFE_TS_RE.match(ts):
            return []
        for db_file in _ADM_DB_FILES:
            snap_path = os.path.join(_ADM_CP_DIR, f"{tag}_{ts}_{db_file}")
            if os.path.exists(snap_path):
                snapshot_files.append((db_file, snap_path))
        return snapshot_files

    if source == 'weekly_backup':
        week_id = str(group_key or '')
        if not _WEEK_ID_RE.match(week_id):
            return []
        for base, db_file in _DB_BASE_TO_LIVE.items():
            snap_path = os.path.join(_ADM_BACKUP_DIR, f"{base}_backup_{week_id}.json")
            if os.path.exists(snap_path):
                snapshot_files.append((db_file, snap_path))
        return snapshot_files

    if source == 'legacy_backup':
        fname = os.path.basename(str(group_key or ''))
        if not _SAFE_FILENAME_RE.match(fname):
            return []
        db_file = _infer_live_db_from_backup_name(fname)
        if not db_file:
            return []
        snap_path = os.path.join(_ADM_BACKUP_DIR, fname)
        if os.path.exists(snap_path):
            snapshot_files.append((db_file, snap_path))
        return snapshot_files

    return []


def _get_record_label(record):
    if not isinstance(record, dict):
        return str(record)[:60]
    for field in ['name', 'full_name', 'username', 'phone', 'service_name', 'drug_name']:
        val = record.get(field)
        if val:
            return str(val)[:60]
    keys = list(record.keys())[:3]
    return ', '.join(keys)


def _flatten_tinydb(data):
    flat = {}
    if not isinstance(data, dict):
        return flat
    for table_name, table_data in data.items():
        if isinstance(table_data, dict):
            for doc_id, record in table_data.items():
                flat[f"{table_name}/{doc_id}"] = record
    return flat


def _compute_db_diff(db_file, checkpoint_data, live_data):
    result = {'db_file': db_file, 'changed': 0, 'added': 0, 'removed': 0, 'records': []}
    cp_flat = _flatten_tinydb(checkpoint_data)
    live_flat = _flatten_tinydb(live_data)
    all_keys = sorted(set(cp_flat.keys()) | set(live_flat.keys()))
    for key in all_keys:
        cp_val = cp_flat.get(key)
        live_val = live_flat.get(key)
        if cp_val is None:
            result['added'] += 1
            result['records'].append({
                'key': key, 'status': 'added',
                'label': _get_record_label(live_val), 'diff_lines': [],
            })
        elif live_val is None:
            result['removed'] += 1
            result['records'].append({
                'key': key, 'status': 'removed',
                'label': _get_record_label(cp_val), 'diff_lines': [],
            })
        elif cp_val != live_val:
            result['changed'] += 1
            cp_lines = json.dumps(cp_val, ensure_ascii=False, indent=2).splitlines(keepends=True)
            live_lines = json.dumps(live_val, ensure_ascii=False, indent=2).splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                cp_lines, live_lines,
                fromfile=f"checkpoint/{key}",
                tofile=f"current/{key}",
                lineterm='',
            ))
            truncated = len(diff) > 300
            result['records'].append({
                'key': key, 'status': 'changed',
                'label': _get_record_label(live_val),
                'diff_lines': diff[:300],
                'truncated': truncated,
                'total_lines': len(diff),
            })
    return result


@admin_bp.route('/admin/checkpoints')
def checkpoints_page():
    groups = _list_restore_groups()
    return render_template('admin_checkpoint_restore.html', groups=groups)


@admin_bp.route('/api/admin/checkpoint/diff', methods=['POST'])
def checkpoint_diff():
    body = request.get_json(silent=True) or {}
    source = body.get('source', '')
    group_key = body.get('group_key', '')

    # Backward compatibility for already-open page scripts.
    if not source and body.get('tag') and body.get('timestamp'):
        source = 'checkpoint'
        group_key = f"{body.get('tag')}||{body.get('timestamp')}"

    snapshot_files = _resolve_snapshot_files(source, group_key)
    if not snapshot_files:
        return jsonify({'error': 'No matching backup files found'}), 400

    summary = {
        'total_changed': 0, 'total_added': 0, 'total_removed': 0, 'files_compared': []
    }
    diffs = []
    for db_file, cp_path in snapshot_files:
        live_path = os.path.join(_ADM_ROOT, db_file)
        try:
            cp_data = _read_db_snapshot(cp_path)
            live_data = _read_db_snapshot(live_path) if os.path.exists(live_path) else {}
        except Exception as exc:
            diffs.append({'db_file': db_file, 'error': str(exc), 'records': []})
            continue
        file_diff = _compute_db_diff(db_file, cp_data, live_data)
        summary['total_changed'] += file_diff['changed']
        summary['total_added'] += file_diff['added']
        summary['total_removed'] += file_diff['removed']
        summary['files_compared'].append(db_file)
        diffs.append(file_diff)
    return jsonify({'summary': summary, 'diffs': diffs})


@admin_bp.route('/api/admin/checkpoint/restore', methods=['POST'])
def restore_checkpoint():
    body = request.get_json(silent=True) or {}
    source = body.get('source', '')
    group_key = body.get('group_key', '')

    # Backward compatibility for already-open page scripts.
    if not source and body.get('tag') and body.get('timestamp'):
        source = 'checkpoint'
        group_key = f"{body.get('tag')}||{body.get('timestamp')}"

    snapshot_files = _resolve_snapshot_files(source, group_key)
    if not snapshot_files:
        return jsonify({'error': 'No matching backup files found'}), 400

    confirmed = body.get('confirm', False)
    if not confirmed:
        return jsonify({'error': 'Must confirm restore'}), 400

    if not check_password_hash(current_user.password_hash, body.get('admin_password', '')):
        abort(403, description='Cần xác nhận mật khẩu quản trị viên trước khi khôi phục.')
    # Authenticate and parse the entire set before touching any live file.
    prepared = [(db_file, _read_db_snapshot(cp_path)) for db_file, cp_path in snapshot_files]

    now_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    safety_dir = os.path.abspath(os.path.join(_ADM_ROOT, 'backups', 'pre_restore_safety'))
    os.makedirs(safety_dir, exist_ok=True)
    for db_file in _ADM_DB_FILES:
        live_path = os.path.join(_ADM_ROOT, db_file)
        if os.path.exists(live_path):
            shutil.copy(live_path, os.path.join(safety_dir, f"pre_restore_{now_ts}_{db_file}"))

    restored = []
    errors = []
    for db_file, snapshot_data in prepared:
        live_path = os.path.join(_ADM_ROOT, db_file)
        try:
            _write_live_db_snapshot(live_path, snapshot_data)
            restored.append(db_file)
        except Exception as exc:
            errors.append(f"{db_file}: {str(exc)}")

    if errors:
        return jsonify({'success': False, 'errors': errors, 'restored': restored}), 500

    users_table.clear_cache()
    for user in users_table.all():
        users_table.update({'auth_version': uuid.uuid4().hex}, doc_ids=[user.doc_id])

    from utils.db_logger import log_action
    log_action('db_restore', {
        'restore_source': source,
        'restore_group_key': group_key,
        'restored_files': restored,
        'safety_backup_ts': now_ts,
        'restored_by': current_user.username,
    })
    return jsonify({'success': True, 'restored': restored, 'safety_backup_ts': now_ts})


def _full_backup_directory():
    from pathlib import Path
    return Path(os.getenv('QKB_BACKUP_DIR') or os.path.join(_ADM_ROOT, 'backups', 'full')).resolve()


@admin_bp.route('/admin/backups', methods=['GET', 'POST'])
def full_backups():
    from utils.full_backup import create_backup
    if request.method == 'POST':
        create_backup(_ADM_ROOT, _full_backup_directory())
        return redirect(url_for('admin.full_backups'))
    directory = _full_backup_directory()
    files = sorted((p.name for p in directory.glob('qkb_*.qkb') if p.is_file()), reverse=True)
    status_path = os.path.join(_ADM_ROOT, 'backups', 'status.json')
    status = {}
    if os.path.exists(status_path):
        with open(status_path, encoding='utf-8') as stream:
            status = json.load(stream)
    from datetime import timezone
    last = status.get('last_success')
    status['stale'] = not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() > 1200
    return render_template('full_backups.html', files=files, status=status)


@admin_bp.route('/admin/backups/<filename>')
def download_full_backup(filename):
    if not re.fullmatch(r'qkb_[0-9TZ]+_[a-f0-9]{8}\.qkb', filename):
        abort(404)
    from utils.full_backup import portable_backup
    from flask import send_file
    path = _full_backup_directory() / filename
    if not path.is_file():
        abort(404)
    stream = portable_backup(path)
    response = send_file(stream, mimetype='application/zip', as_attachment=True, download_name=filename)
    response.call_on_close(stream.close)
    return response


@admin_bp.route('/admin/backups/<filename>/restore', methods=['POST'])
def restore_full_backup(filename):
    from utils.full_backup import create_backup, restore_backup
    from flask import session
    if not re.fullmatch(r'qkb_[0-9TZ]+_[a-f0-9]{8}\.qkb', filename):
        abort(404)
    if request.form.get('confirmation') != 'RESTORE' or not check_password_hash(current_user.password_hash, request.form.get('admin_password', '')):
        abort(403, description='Nhập RESTORE và mật khẩu quản trị viên để khôi phục.')
    path = _full_backup_directory() / filename
    if not path.is_file():
        abort(404)
    # The global gate blocks all requests until restore and cache refresh finish.
    from utils.full_backup import inspect_backup
    inspect_backup(path)
    create_backup(_ADM_ROOT, _full_backup_directory())
    restore_backup(_ADM_ROOT, path)
    from shared_db import DATABASES
    for database in DATABASES:
        for table in database.tables():
            database.table(table).clear_cache()
            database.table(table)._next_id = None
    for user in users_table.all():
        users_table.update({'auth_version': uuid.uuid4().hex}, doc_ids=[user.doc_id])
    session.clear()
    return redirect(url_for('auth.login'))
