from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required
from tinydb import Query
from werkzeug.utils import secure_filename
import os
import re
import shutil
from datetime import datetime

from shared_db import patients_table as patients
from utils.error_logger import append_error_log
from utils.pdf_generator import generate_exam_file_name
from utils.db_logger import weekly_backup_all, log_action

patients_bp = Blueprint('patients', __name__)

# Patients
Patients = Query()

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATIENT_IMAGE_ROOT = os.path.abspath(os.path.join(_APP_ROOT, 'uploads', 'patient_image'))
_PDF_ROOT = os.path.abspath(os.path.join(_APP_ROOT, 'files', 'pdf'))
_JPEG_ROOT = os.path.abspath(os.path.join(_APP_ROOT, 'files', 'jpeg'))
_CHECKPOINT_DIR = os.path.abspath(os.path.join(_APP_ROOT, 'backups', 'checkpoints'))


def _normalize_phone_input(value):
    text = str(value or '').strip()
    # Requested normalization: trim and convert internal spaces to underscores.
    text = re.sub(r'\s+', '_', text)
    text = text.replace('/', '_').replace('\\', '_')
    text = re.sub(r'[\x00-\x1f]', '', text)
    return text


def _safe_image_folder_token(phone_text):
    return secure_filename(str(phone_text or 'unknown')) or 'unknown'


def _safe_image_name_token(phone_text):
    token = secure_filename(str(phone_text or '')).strip('._')
    return token or 'patient'


def _safe_exam_date_token(value):
    token = secure_filename(str(value or '')).strip('._')
    return token or 'date'


def _is_within(base_dir, candidate_path):
    try:
        base_abs = os.path.realpath(os.path.abspath(base_dir))
        cand_abs = os.path.realpath(os.path.abspath(candidate_path))
        return os.path.commonpath([base_abs, cand_abs]) == base_abs
    except Exception:
        return False


def _resolve_to_abs(path_value):
    path_text = str(path_value or '').strip()
    if not path_text:
        return None
    if os.path.isabs(path_text):
        return os.path.abspath(path_text)
    return os.path.abspath(os.path.join(_APP_ROOT, path_text))


def _rename_path_safe(old_abs, new_abs, allowed_root):
    if not old_abs or not new_abs:
        return False
    if not _is_within(allowed_root, old_abs) or not _is_within(allowed_root, new_abs):
        return False
    if old_abs == new_abs:
        return os.path.exists(old_abs)
    if not os.path.exists(old_abs):
        return False
    if os.path.exists(new_abs):
        return False

    old_ext = os.path.splitext(old_abs)[1].lower()
    new_ext = os.path.splitext(new_abs)[1].lower()
    if old_ext and new_ext and old_ext != new_ext:
        return False

    # Defense-in-depth: do not create/write through symlinked destination parents.
    dest_parent = os.path.dirname(new_abs)
    if os.path.islink(dest_parent):
        return False

    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    os.replace(old_abs, new_abs)
    return True


def _web_url_from_abs(path_abs):
    if not path_abs:
        return None
    normalized = os.path.abspath(path_abs).replace('\\', '/')
    app_root_normalized = _APP_ROOT.replace('\\', '/')
    if not normalized.startswith(app_root_normalized + '/'):
        return None
    rel = normalized[len(app_root_normalized) + 1:]
    rel = rel.replace('\\', '/')
    if rel.startswith('uploads/'):
        return '/' + rel
    if rel.startswith('files/pdf/'):
        return '/' + rel
    if rel.startswith('files/jpeg/'):
        return '/' + rel
    return None


def _file_exists_abs(path_abs):
    try:
        return bool(path_abs and os.path.exists(path_abs))
    except Exception:
        return False


def _is_duplicate_phone(phone_text, current_patient_id):
    dupes = []
    for p in patients.all():
        if p.get('id') == current_patient_id:
            continue
        if _normalize_phone_input(p.get('phone', '')) == phone_text:
            dupes.append({
                'patient_id': p.get('id'),
                'kid_name': p.get('kid_name', ''),
                'parent_name': p.get('name', ''),
                'phone': p.get('phone', ''),
            })
    return dupes


def _create_db_checkpoint(tag='phone_rename'):
    os.makedirs(_CHECKPOINT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    copied = []
    for db_file in ['db.json', 'db_services.json', 'money_log.json', 'db_mua_thuoc.json']:
        src = os.path.join(_APP_ROOT, db_file)
        if not os.path.exists(src):
            continue
        dst = os.path.join(_CHECKPOINT_DIR, f"{tag}_{ts}_{db_file}")
        shutil.copy(src, dst)
        copied.append(dst)

    log_action('db_checkpoint', {
        'tag': tag,
        'timestamp': ts,
        'files': copied,
    })
    return copied


def _validate_patient_exam_shape(exams):
    if not isinstance(exams, list):
        return False, 'exams must be a list'
    for exam in exams:
        if not isinstance(exam, dict):
            return False, 'exam must be an object'
        images = exam.get('images', [])
        if images is None:
            continue
        if not isinstance(images, list):
            return False, 'exam.images must be a list'
        for img in images:
            if not isinstance(img, dict):
                return False, 'exam.images item must be an object'
            if 'filename' in img and not isinstance(img.get('filename'), str):
                return False, 'exam.images.filename must be string'
            if 'path' in img and not isinstance(img.get('path'), str):
                return False, 'exam.images.path must be string'
    return True, None


def _build_phone_rename_plan(patient_doc, old_phone, new_phone):
    exams = patient_doc.get('exams', [])
    plan = []
    if not isinstance(exams, list):
        return plan

    old_folder_token = _safe_image_folder_token(old_phone)
    new_folder_token = _safe_image_folder_token(new_phone)
    new_image_name_token = _safe_image_name_token(new_phone)

    for exam in exams:
        if not isinstance(exam, dict):
            continue

        exam_id = str(exam.get('id') or '')
        exam_date = exam.get('exam_date')
        date_token = _safe_exam_date_token(exam_date)

        images = exam.get('images', [])
        if isinstance(images, list):
            for img_idx, img in enumerate(images):
                if not isinstance(img, dict):
                    continue

                old_filename = str(img.get('filename') or '').strip()
                old_rel_path = str(img.get('path') or '').strip()
                if not old_rel_path and old_filename:
                    old_rel_path = os.path.join('uploads', 'patient_image', old_folder_token, old_filename)

                _, ext = os.path.splitext(old_filename)
                if not ext:
                    _, ext = os.path.splitext(old_rel_path)
                ext = (ext or '.jpg').lower()

                new_filename = f"{new_image_name_token}_{date_token}_image_{img_idx + 1}{ext}"
                new_rel_path = os.path.join('uploads', 'patient_image', new_folder_token, new_filename)

                old_abs = _resolve_to_abs(old_rel_path)
                new_abs = _resolve_to_abs(new_rel_path)
                if old_abs and new_abs and old_abs != new_abs:
                    plan.append({
                        'kind': 'image',
                        'exam_id': exam_id,
                        'image_idx': img_idx,
                        'old_name': os.path.basename(old_abs),
                        'new_name': os.path.basename(new_abs),
                        'old_abs': old_abs,
                        'new_abs': new_abs,
                        'old_url': _web_url_from_abs(old_abs),
                        'new_url': _web_url_from_abs(new_abs),
                    })

        legacy_path = exam.get('image_path')
        if legacy_path:
            old_legacy_abs = _resolve_to_abs(legacy_path)
            old_legacy_name = os.path.basename(str(legacy_path).strip())
            _, legacy_ext = os.path.splitext(old_legacy_name)
            legacy_ext = (legacy_ext or '.jpg').lower()
            new_legacy_name = f"{new_image_name_token}_{date_token}_image_1{legacy_ext}"
            new_legacy_rel = os.path.join('uploads', 'patient_image', new_folder_token, new_legacy_name)
            new_legacy_abs = _resolve_to_abs(new_legacy_rel)

            if old_legacy_abs and new_legacy_abs and old_legacy_abs != new_legacy_abs:
                plan.append({
                    'kind': 'image_legacy',
                    'exam_id': exam_id,
                    'old_name': os.path.basename(old_legacy_abs),
                    'new_name': os.path.basename(new_legacy_abs),
                    'old_abs': old_legacy_abs,
                    'new_abs': new_legacy_abs,
                    'old_url': _web_url_from_abs(old_legacy_abs),
                    'new_url': _web_url_from_abs(new_legacy_abs),
                })

        if exam_id and exam_date:
            short_exam_id = exam_id[:8].replace('-', '')
            old_base = generate_exam_file_name(old_phone, exam_date, short_exam_id)
            new_base = generate_exam_file_name(new_phone, exam_date, short_exam_id)

            old_pdf = os.path.join(_PDF_ROOT, f"{old_base}.pdf")
            new_pdf = os.path.join(_PDF_ROOT, f"{new_base}.pdf")
            if old_pdf != new_pdf:
                plan.append({
                    'kind': 'pdf',
                    'exam_id': exam_id,
                    'old_name': os.path.basename(old_pdf),
                    'new_name': os.path.basename(new_pdf),
                    'old_abs': old_pdf,
                    'new_abs': new_pdf,
                    'old_url': _web_url_from_abs(old_pdf),
                    'new_url': _web_url_from_abs(new_pdf),
                })

            old_jpeg = os.path.join(_JPEG_ROOT, f"{old_base}.jpg")
            new_jpeg = os.path.join(_JPEG_ROOT, f"{new_base}.jpg")
            if old_jpeg != new_jpeg:
                plan.append({
                    'kind': 'jpeg',
                    'exam_id': exam_id,
                    'old_name': os.path.basename(old_jpeg),
                    'new_name': os.path.basename(new_jpeg),
                    'old_abs': old_jpeg,
                    'new_abs': new_jpeg,
                    'old_url': _web_url_from_abs(old_jpeg),
                    'new_url': _web_url_from_abs(new_jpeg),
                })

    return plan


def _rename_patient_assets(patient_doc, old_phone, new_phone):
    exams = patient_doc.get('exams', [])
    if not isinstance(exams, list):
        return

    plan = _build_phone_rename_plan(patient_doc, old_phone, new_phone)
    for step in plan:
        kind = step.get('kind')
        old_abs = step.get('old_abs')
        new_abs = step.get('new_abs')

        if kind in ('image', 'image_legacy'):
            renamed = _rename_path_safe(old_abs, new_abs, _PATIENT_IMAGE_ROOT)
            if not (renamed or _file_exists_abs(new_abs)):
                continue

            exam_id = step.get('exam_id')
            for exam in exams:
                if str(exam.get('id') or '') != exam_id:
                    continue
                if kind == 'image':
                    img_idx = step.get('image_idx', 0)
                    images = exam.get('images', [])
                    if img_idx < len(images) and isinstance(images[img_idx], dict):
                        images[img_idx]['filename'] = os.path.basename(new_abs)
                        images[img_idx]['path'] = os.path.relpath(new_abs, _APP_ROOT)
                else:
                    exam['image_path'] = os.path.relpath(new_abs, _APP_ROOT)
                break

        elif kind == 'pdf':
            _rename_path_safe(old_abs, new_abs, _PDF_ROOT)
        elif kind == 'jpeg':
            _rename_path_safe(old_abs, new_abs, _JPEG_ROOT)


@patients_bp.route('/api/patient/<patient_id>/phone-rename-preview', methods=['POST'])
@login_required
def phone_rename_preview(patient_id):
    try:
        results = patients.search(Query().id == patient_id)
        if not results:
            return jsonify({'status': 'error', 'message': 'Patient not found'}), 404

        patient = results[0]
        data = request.get_json(silent=True) or {}
        new_phone = _normalize_phone_input(data.get('new_phone', ''))
        old_phone = patient.get('phone', '')

        duplicates = _is_duplicate_phone(new_phone, patient_id)
        plan = _build_phone_rename_plan(patient, old_phone, new_phone)

        preview_rows = []
        for step in plan:
            old_abs = step.get('old_abs')
            new_abs = step.get('new_abs')
            preview_rows.append({
                'kind': step.get('kind'),
                'exam_id': step.get('exam_id'),
                'old_name': step.get('old_name'),
                'new_name': step.get('new_name'),
                'old_exists': _file_exists_abs(old_abs),
                'new_exists': _file_exists_abs(new_abs),
                'old_url': step.get('old_url'),
                'new_url': step.get('new_url'),
            })

        log_action('phone_rename_preview', {
            'patient_id': patient_id,
            'old_phone': old_phone,
            'new_phone': new_phone,
            'rows': len(preview_rows),
            'duplicate_count': len(duplicates),
        })

        return jsonify({
            'status': 'success',
            'old_phone': old_phone,
            'new_phone': new_phone,
            'duplicate': len(duplicates) > 0,
            'duplicates': duplicates,
            'rows': preview_rows,
        })
    except Exception as e:
        append_error_log(
            'Phone rename preview failed',
            str(e),
            {
                'route': '/api/patient/<patient_id>/phone-rename-preview',
                'patient_id': patient_id,
            }
        )
        return jsonify({'status': 'error', 'message': 'Không thể tạo bản xem trước lúc này.'}), 500


@patients_bp.route('/patients', methods=['GET', 'POST'])
def manage_patients():
    if request.method == 'POST':
        try:
            kid_name = request.form.get('kid_name', '')
            kid_birthdate = request.form.get('kid_birthdate', '')
            name = request.form.get('name', '')
            phone = _normalize_phone_input(request.form.get('phone', ''))
            address = request.form.get('address', '')

            import uuid
            patients.insert({
                'id': str(uuid.uuid4()),
                'kid_name': kid_name,
                'kid_birthday': kid_birthdate,
                'name': name,
                'phone': phone,
                'address': address,
                'last_visit': '',
                'exams': []
            })
            return redirect(url_for('patients.manage_patients'))
        except Exception as e:
            append_error_log(
                'Patient create failed',
                str(e),
                {
                    'route': '/patients',
                    'action': 'create',
                    'name': request.form.get('name', ''),
                    'phone': request.form.get('phone', ''),
                }
            )
            return 'Error while creating patient', 500
    return render_template('patients.html', patients=patients.all())


@patients_bp.route('/patient/<patient_id>')
def exam_patient(patient_id):
    # Find patient by UUID
    results = patients.search(Query().id == patient_id)
    if not results:
        return "Lỗi kết nối /patient/<patient_id>: Not Found", 404
    patient = results[0]

    # Later: redirect to exam screen
    return render_template('exam.html', patient=patient)


# edit patients info
@patients_bp.route('/edit_patient/<patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    results = patients.search(Query().id == patient_id)
    if not results:
        return "Patient not found", 404
    patient = results[0]

    if request.method == 'POST':
        try:
            action = request.form.get('action')
            if action == 'update':
                new_phone = _normalize_phone_input(request.form.get('phone', ''))
                old_phone = patient.get('phone', '')
                next_exams = patient.get('exams', [])

                duplicates = _is_duplicate_phone(new_phone, patient_id)
                if duplicates:
                    return render_template(
                        'edit_patient.html',
                        patient=patient,
                        error_message='SĐT/Mã đã trùng với bệnh nhân khác. Vui lòng kiểm tra trước khi lưu.',
                        duplicate_patients=duplicates
                    )

                if new_phone != old_phone:
                    if request.form.get('rename_confirmed') != '1':
                        return render_template(
                            'edit_patient.html',
                            patient=patient,
                            error_message='Vui lòng xem trước và xác nhận đổi tên file trước khi lưu.'
                        )

                    weekly_backup_all()
                    checkpoint_files = _create_db_checkpoint(tag='patient_phone_rename')

                    mutable_patient = {
                        **dict(patient),
                        'exams': next_exams
                    }
                    _rename_patient_assets(mutable_patient, old_phone, new_phone)
                    next_exams = mutable_patient.get('exams', next_exams)

                    valid, reason = _validate_patient_exam_shape(next_exams)
                    if not valid:
                        return render_template(
                            'edit_patient.html',
                            patient=patient,
                            error_message=f'Không lưu được vì dữ liệu toa khám không hợp lệ: {reason}'
                        )

                    log_action('phone_rename_apply', {
                        'patient_id': patient_id,
                        'old_phone': old_phone,
                        'new_phone': new_phone,
                        'checkpoint_files': checkpoint_files,
                    })

                patients.update({
                    'kid_name': request.form.get('kid_name', ''),
                    'kid_birthday': request.form.get('kid_birthday', ''),
                    'name': request.form.get('name', ''),
                    'phone': new_phone,
                    'address': request.form.get('address', ''),
                    'exams': next_exams
                }, Query().id == patient_id)
            elif action == 'delete':
                patients.remove(Query().id == patient_id)
            return redirect(url_for('patients.manage_patients'))
        except Exception as e:
            append_error_log(
                'Patient edit failed',
                str(e),
                {
                    'route': '/edit_patient/<patient_id>',
                    'action': request.form.get('action'),
                    'patient_id': patient_id,
                    'name': request.form.get('name', ''),
                    'phone': request.form.get('phone', ''),
                }
            )
            return 'Error while editing patient', 500
    return render_template('edit_patient.html', patient=patient)


@patients_bp.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        try:
            kid_name = request.form.get('kid_name', '')
            kid_birthday = request.form.get('kid_birthday', '')
            name = request.form.get('name', '')
            phone = _normalize_phone_input(request.form.get('phone', ''))
            address = request.form.get('address', '')

            import uuid
            patients.insert({
                'id': str(uuid.uuid4()),
                'kid_name': kid_name,
                'kid_birthday': kid_birthday,
                'name': name,
                'phone': phone,
                'address': address,
                'last_visit': '',
                'exams': []
            })
            return redirect(url_for('patients.manage_patients'))
        except Exception as e:
            append_error_log(
                'Patient add failed',
                str(e),
                {
                    'route': '/add_patient',
                    'action': 'create',
                    'name': request.form.get('name', ''),
                    'phone': request.form.get('phone', ''),
                }
            )
            return 'Error while adding patient', 500
    return render_template('add_patient.html')


@patients_bp.route('/patient/<patient_id>/exams')
def view_exams(patient_id):
    results = patients.search(Query().id == patient_id)
    if not results:
        return "Patient not found", 404
    patient = results[0]

    # Get all exams for this patient
    patient_exams = patient.get("exams", [])

    def exam_sort_key(e):
        return (
            e.get('exam_date', ''),
            e.get('submit_time', '')
        )
    patient_exams = sorted(patient_exams, key=exam_sort_key, reverse=True)

    # Render the renamed template
    return render_template('previous_exams.html', patient=patient, exams=patient_exams)
