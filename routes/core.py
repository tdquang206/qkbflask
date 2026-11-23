from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, jsonify, abort, session, current_app
from flask_login import current_user

from shared_db import patients_table as patients, exams_table as exams
from utils.db_logger import weekly_backup_all, log_action
from utils.omni_search import run_omni_search
from utils.exam_access import can_edit_exam
import time
import hashlib
from werkzeug.exceptions import HTTPException


core_bp = Blueprint('core', __name__)


@core_bp.before_app_request
def require_login():
    """Require login for all non-auth, non-static endpoints."""
    if request.endpoint and (request.endpoint.startswith('static') or request.endpoint.startswith('auth.')):
        return

    if not current_user.is_authenticated:
        if request.method not in ('GET', 'HEAD') or request.path.startswith('/api/'):
            return jsonify(status='error', message='Phiên đăng nhập đã hết. Đăng nhập lại rồi thử lưu; nội dung chưa được lưu.'), 401
        return redirect(url_for('auth.login', next=request.url))

    now = time.time()
    if (now - session.get('last_activity', now) > 1800
            or now - session.get('authenticated_at', now) > 8 * 3600
            or (current_app.config.get('LAN_MODE') and 'authenticated_at' not in session)):
        session.clear()
        return jsonify(status='error', message='Phiên đăng nhập đã hết. Nội dung chưa được lưu.'), 401
    session['last_activity'] = now
    if session.get('must_change_password'):
        if request.method not in ('GET', 'HEAD'):
            return jsonify(status='error', message='Cần đổi mật khẩu tại /account/password trước khi tiếp tục. Nội dung chưa được lưu.'), 401
        return redirect(url_for('auth.change_password'))

    endpoint = request.endpoint or ''
    role = getattr(current_user, 'role', 'user')
    medical = role in ('doctor', 'admin')
    mutable = request.method not in ('GET', 'HEAD', 'OPTIONS')
    if endpoint.startswith(('exam.', 'comparisons.')) or endpoint in ('core.all_exams', 'core.omni_search', 'core.uploaded_file', 'core.serve_pdf', 'core.serve_jpeg', 'patients.view_exams', 'patients.exam_patient'):
        if not medical:
            abort(403)
    if endpoint.startswith('settings.') and endpoint != 'settings.changelog':
        if role != 'admin' and not (request.method == 'GET' and endpoint == 'settings.api_services' and medical):
            abort(403)
    if endpoint.startswith('reports.') or endpoint == 'route_all_exams_page.mark_paid':
        if role not in ('admin', 'cashier'):
            abort(403)
    if endpoint == 'route_all_exams_page.get_exam_list' and role not in ('admin', 'doctor', 'cashier'):
        abort(403)
    if endpoint == 'patients.manage_patients' and role not in ('admin', 'doctor', 'receptionist', 'cashier'):
        abort(403)
    if mutable and endpoint.startswith(('drugs.', 'mua_thuoc.')) and role not in ('admin', 'pharmacist'):
        abort(403)
    if endpoint in ('patients.manage_packages', 'patients.view_package_usage') and role not in ('admin', 'doctor', 'cashier'):
        abort(403)
    if mutable and endpoint == 'patients.manage_packages' and role not in ('admin', 'cashier'):
        abort(403)
    if mutable and endpoint.startswith('patients.') and endpoint != 'patients.manage_packages' and role not in ('admin', 'doctor', 'receptionist'):
        abort(403)


@core_bp.after_app_request
def audit_response(response):
    """Allowlisted audit only; full backups run between requests."""
    clinical_read = request.method == 'GET' and current_user.is_authenticated and request.endpoint in {
        'patients.view_exams', 'exam.edit_exam', 'exam.exam_history', 'core.uploaded_file',
        'core.serve_pdf', 'core.serve_jpeg', 'core.omni_search', 'comparisons.catalog', 'comparisons.download_comparison'}
    if request.method in ['POST', 'PUT', 'PATCH', 'DELETE'] or clinical_read:
        identifiers = {key: value for key, value in (request.view_args or {}).items() if key in ('patient_id', 'exam_id', 'comparison_id')}
        filename = (request.view_args or {}).get('filename')
        if filename:
            identifiers['asset_ref'] = hashlib.sha256(filename.encode('utf-8')).hexdigest()
        log_action('read' if clinical_read else 'write', {
            'endpoint': request.endpoint,
            'method': request.method,
            'actor_id': current_user.id if current_user.is_authenticated else None,
            'status_code': response.status_code,
            **identifiers,
        })
    if request.endpoint != 'static':
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
    return response


@core_bp.app_errorhandler(HTTPException)
def http_error(error):
    if request.method not in ('GET', 'HEAD') or request.path.startswith('/api/'):
        return jsonify(status='error', message=error.description), error.code
    return render_template('http_error.html', error=error), error.code


@core_bp.app_context_processor
def clinical_permissions():
    return {'can_edit_exam': can_edit_exam}


@core_bp.app_template_filter('clinic_time')
def clinic_time(value):
    from datetime import datetime, timedelta, timezone
    if not value:
        return ''
    return datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M:%S')


@core_bp.route('/')
def index():
    return render_template('index.html')


@core_bp.route('/exams')
def all_exams():
    return render_template('exams.html', exams=exams.all(), patients=patients)


@core_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded images from the uploads folder."""
    return send_from_directory('uploads', filename)


@core_bp.route('/files/pdf/<path:filename>')
def serve_pdf(filename):
    """Serve generated PDF files."""
    return send_from_directory('files/pdf', filename)


@core_bp.route('/files/jpeg/<path:filename>')
def serve_jpeg(filename):
    return send_from_directory('files/jpeg', filename)


@core_bp.route('/api/omni-search')
def omni_search():
    """
    Omni-search endpoint.
    Query param: q (string, min 3 chars after normalisation)
    Returns grouped results across patients, exams, drugs, and purchases.
    """
    query = request.args.get('q', '').strip()
    return jsonify(run_omni_search(query))
