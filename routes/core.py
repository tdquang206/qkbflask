from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_login import current_user

from shared_db import patients_table as patients, exams_table as exams
from utils.db_logger import weekly_backup_all, log_action
from utils.omni_search import run_omni_search


core_bp = Blueprint('core', __name__)


@core_bp.before_app_request
def require_login():
    """Require login for all non-auth, non-static endpoints."""
    if request.endpoint and (request.endpoint.startswith('static') or request.endpoint.startswith('auth.')):
        return

    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.url))


@core_bp.after_app_request
def auto_log_and_backup(response):
    """Backup and audit write operations globally."""
    if request.method in ['POST', 'PUT', 'DELETE']:
        weekly_backup_all()
        log_action('auto', {
            'endpoint': request.endpoint,
            'method': request.method,
            'path': request.path,
            'form': request.form.to_dict(),
            'args': request.args.to_dict()
        })
    return response


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


@core_bp.route('/api/omni-search')
def omni_search():
    """
    Omni-search endpoint.
    Query param: q (string, min 3 chars after normalisation)
    Returns grouped results across patients, exams, drugs, and purchases.
    """
    query = request.args.get('q', '').strip()
    return jsonify(run_omni_search(query))
