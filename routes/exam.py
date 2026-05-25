from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort, flash
from flask_login import current_user
from datetime import datetime
from tinydb import Query
import uuid
from werkzeug.utils import secure_filename
import os, io, json
from routes.settings import load_settings
from PIL import Image
import requests

from utils.template_renderer import render_exam_markdown
from utils.pdf_generator import build_exam_html, generate_pdf_and_jpeg, delete_exam_files, generate_exam_file_name
from utils.error_logger import append_error_log

exam_bp = Blueprint('exam', __name__)
from shared_db import db, patients_table as Patients_db, services_table

# for image
MAX_SIZE = (2000, 2000)
MAX_FILE_SIZE = 1 * 1024 * 1024
SETTINGS_FILE = 'user_settings.json'
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _json_server_error(message='Đã có lỗi hệ thống, vui lòng thử lại sau.'):
    return jsonify({"status": "error", "message": message}), 500


def _safe_patient_image_folder(phone):
    safe_phone = secure_filename(str(phone or 'unknown')) or 'unknown'
    folder = os.path.join('uploads', 'patient_image', safe_phone)
    os.makedirs(folder, exist_ok=True)
    return folder


def _is_allowed_image_ext(ext):
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _safe_filename_token(value, fallback='x'):
    token = secure_filename(str(value or '')).strip('._')
    return token or fallback

def _to_float(value, default=0.0):
    try:
        if value is None:
            return default
        text = str(value).strip().replace(',', '')
        if text == '':
            return default
        return float(text)
    except Exception:
        return default

def _package_is_active(pkg, exam_date=None):
    """Check if package is active (not expired)"""
    expires_at = pkg.get('expires_at')
    if not expires_at:
        result = True
    else:
        if not exam_date:
            result = True
        else:
            try:
                expiry = datetime.strptime(expires_at, '%Y-%m-%d').date()
                exam_dt = datetime.strptime(exam_date, '%Y-%m-%d').date() if isinstance(exam_date, str) else exam_date.date()
                result = exam_dt <= expiry
            except:
                result = True
    print(f"Processed package active check for service {pkg.get('service_id')}: {'active' if result else 'expired'}.")
    return result

def _package_display_status(pkg, exam_date=None):
    """Get display status for package"""
    remaining = pkg.get('remaining_sessions', 0)
    if remaining <= 0:
        status = 'Hết lượt'
    elif not _package_is_active(pkg, exam_date):
        status = 'Hết hạn'
    else:
        status = f'Còn {remaining} lượt'
    print(f"Processed package display status for service {pkg.get('service_id')}: {status}.")
    return status

def _collect_services_from_form(form, patient_packages, exam_date=None):
    service_ids = form.getlist('service_id')
    service_names = form.getlist('service_name')
    service_prices = form.getlist('service_price')
    service_quantities = form.getlist('service_quantity')
    service_notes = form.getlist('service_note')

    services = []
    all_services = {str(s.get('id')): s for s in services_table.all() if s.get('id') is not None}

    for idx, sid in enumerate(service_ids):
        sid = (sid or '').strip()
        if not sid:
            continue

        raw_name = service_names[idx] if idx < len(service_names) else ''
        raw_price = service_prices[idx] if idx < len(service_prices) else ''
        raw_quantity = service_quantities[idx] if idx < len(service_quantities) else '1'
        raw_note = service_notes[idx] if idx < len(service_notes) else ''

        catalog = all_services.get(sid, {})
        name = (raw_name or catalog.get('name') or '').strip()
        quantity = int(_to_float(raw_quantity, default=1.0))
        price_val = _to_float(raw_price, default=_to_float(catalog.get('price'), default=0.0))

        prepaid_status = ''
        for pkg in patient_packages:
            if (pkg.get('service_id') == sid and 
                _package_is_active(pkg, exam_date) and 
                pkg.get('remaining_sessions', 0) >= quantity):
                price_val = _to_float(pkg.get('unit_price'), default=price_val)
                pkg['remaining_sessions'] = pkg.get('remaining_sessions', 0) - quantity
                prepaid_status = 'PAID PACKAGE'
                break

        services.append({
            'id': sid, 
            'name': name, 
            'price': price_val, 
            'quantity': quantity, 
            'note': raw_note,
            'prepaid_status': prepaid_status
        })

    print(f"Processed services from form: {len(services)} services collected.")
    return services

def send_discord_helper(patient, exam_data):
    # Load settings
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
    except:
        return

    webhook_url = settings.get('discord_webhook_url')
    if not webhook_url:
        return
    if not webhook_url.startswith((
        'https://discord.com/api/webhooks/',
        'https://discordapp.com/api/webhooks/',
    )):
        return

    # Use template renderer to build message content
    department = exam_data.get('department')
    message_content = render_exam_markdown(patient, exam_data, doctor_name=exam_data.get('created_by_name'), department=department)

    payload = {
        "content": message_content
    }
    
    files = {}
    if settings.get('attach_image'):
        phone = patient.get('phone')
        exam_date = exam_data.get('exam_date')
        short_id = str(exam_data.get('id'))[:8].replace('-', '')
        
        filename = generate_exam_file_name(phone, exam_date, short_id)
        
        base_dir = os.path.dirname(os.path.abspath(__file__)) # routes/
        app_root = os.path.dirname(base_dir)
        jpeg_path = os.path.join(app_root, "files", "jpeg", f"{filename}.jpg")
        
        if os.path.exists(jpeg_path):
            files["file"] = (f"{filename}.jpg", open(jpeg_path, "rb"))
        else:
            payload["content"] += "\n\n(⚠️ Không tìm thấy file ảnh đơn thuốc)"

    try:
        if files:
            requests.post(webhook_url, data=payload, files=files)
            files["file"][1].close()
        else:
            requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Error sending to Discord: {e}")


# NOTE: Read and Edit CRUD code
@exam_bp.route("/exam/edit_exam/<exam_id>", methods=['POST', 'GET'])
def edit_exam(exam_id):

    exam_editting = None
    patient_found = None
    
    # In TinyDB with nested exams, we still have to iterate patients or search exams if we had a separate table.
    # Since structure is nested:
    for patient in Patients_db.all():
        for exam in patient.get('exams', []):
            if exam.get('id') == exam_id:
                exam_editting = exam
                patient_found = patient
                break
    if not exam_editting or not patient_found:
        flash("Unknown exam info", "error")
        # return redirect(url_for('patient.view_patients')) # logic error in original code too?
        return redirect(url_for('patients.manage_patients'))
    
    if request.method == 'GET':
        settings = load_settings()
        departments = settings.get('departments', ["Nhi khoa", "Khám Da liễu"])
        # load available services and patient prepaid packages
        all_services = services_table.all()
        patient_packages = patient_found.get('packages', [])
        # Enrich packages with status
        enriched_packages = []
        for pkg in patient_packages:
            enriched_pkg = pkg.copy()
            enriched_pkg['status'] = _package_display_status(pkg, exam_editting.get('exam_date'))
            enriched_pkg['is_active'] = _package_is_active(pkg, exam_editting.get('exam_date'))
            enriched_packages.append(enriched_pkg)
        return render_template('edit_exam.html', 
            patient=patient_found, 
            exam=exam_editting, 
            departments=departments,
            services=all_services,
            packages=enriched_packages)

    if request.method == 'POST':
        try:
            exam_date = request.form.get('exam_date')
            weight = request.form.get('weight')
            height = request.form.get('height')
            history = request.form.get('history')
            service_fee = request.form.get("service_fee")
            expected_date = request.form.get('expected_date')

            drug_names = request.form.getlist('drug_name')
            drug_quantities = request.form.getlist('drug_quantity')
            drug_notes = request.form.getlist('drug_note')
            drug_prices = request.form.getlist('drug_price')
            send_discord_flag = request.form.get('send_discord')

            drugs = []
            for name, qty, note, price in zip(drug_names, drug_quantities, drug_notes, drug_prices):
                if name.strip():
                    drugs.append({
                        'name': name,
                        'quantity': qty,
                        'note': note,
                        'price': price
                    })

            patient_packages = patient_found.get('packages', [])
            services = _collect_services_from_form(request.form, patient_packages, exam_date)
            total_override = request.form.get('total_override')

            computed_total = 0
            try:
                computed_total += sum(float(d.get('price',0)) * int(d.get('quantity',1)) for d in drugs)
            except Exception:
                pass
            computed_total += sum(s.get('price',0) for s in services)
            if total_override and total_override.strip():
                final_total = total_override
            else:
                final_total = computed_total

            exam_data = {
                'patient_id': patient_found.get('id'),
                'exam_date': exam_date,
                'weight': weight,
                'height': height,
                'history': history,
                'service_fee': service_fee,
                'expected_date': expected_date,
                'drugs': drugs,
                'services': services,
                'paid_status' : False,
                'total_money': final_total,
                'total_override': total_override,
                'submit_time' : datetime.now().strftime('%y%m%d%H%M%S'),
                'id': exam_id,
                'department': exam_editting.get('department', 'Nhi khoa'),
                'created_by_id': exam_editting.get('created_by_id'),
                'created_by_name': exam_editting.get('created_by_name', 'Admin')
            }

            if patient_packages != patient_found.get('packages', []):
                patient_found['packages'] = patient_packages

            image = request.files.get('lab_image')
            if image and image.filename:
                safe_name = secure_filename(image.filename)
                ext = os.path.splitext(safe_name)[1].lower()
                if not _is_allowed_image_ext(ext):
                    return jsonify({"status": "error", "message": "Định dạng ảnh không hợp lệ"}), 400

                try:
                    # Validate that the uploaded file is a real image
                    image.stream.seek(0)
                    pil_image = Image.open(image.stream)
                    pil_image.verify()
                    # Re-open after verify() to get a usable image object
                    image.stream.seek(0)
                    pil_image = Image.open(image.stream)
                except Exception:
                    return jsonify({"status": "error", "message": "File ảnh không hợp lệ"}), 400

                folder = _safe_patient_image_folder(patient_found.get('phone'))
                patient_token = _safe_filename_token(patient_found.get('phone'), fallback='patient')
                date_token = _safe_filename_token(exam_date, fallback='date')
                filename = f"{patient_token}_{date_token}_image_1{ext}"
                image_path = os.path.join(folder, filename)

                # Save processed/validated image to disk
                save_format = pil_image.format or None
                if save_format is not None:
                    pil_image.save(image_path, format=save_format)
                else:
                    pil_image.save(image_path)
                exam_data['image_path'] = image_path

            exams = patient_found.get("exams", [])
            updated = False
            for i, exam in enumerate(exams):
                if exam.get('id') == exam_id:
                    old_date = exam.get('exam_date')
                    short_id = str(exam_id)[:8].replace('-','')
                    if old_date:
                        delete_exam_files(patient_found.get('phone'), old_date, short_id)
                    exams[i].update(exam_data)
                    updated = True
                    break

            if not updated:
                exams.append(exam_data)

            update_fields = {"exams": exams, "last_visit": exam_date}
            if patient_packages is not None:
                update_fields["packages"] = patient_packages
            Patients_db.update(update_fields, doc_ids=[patient_found.doc_id])

            if send_discord_flag:
                pass

            return jsonify({
              "status": "success",
              "message": "Exam updated",
              "exam_id": exam_data['id'],
              "patient_id": patient_found.get('id')
            })
        except Exception as e:
            append_error_log(
                'Exam update failed',
                str(e),
                {
                    'route': '/exam/edit_exam/<exam_id>',
                    'exam_id': exam_id,
                    'patient_id': patient_found.get('id') if patient_found else None,
                    'exam_date': request.form.get('exam_date'),
                }
            )
            return _json_server_error('Không thể cập nhật toa khám lúc này.')

# NOTE: Create
# Create new exam
@exam_bp.route('/exam/<patient_id>/new_exam', methods=['GET', 'POST'])
def new_exam(patient_id):

    # Find patient by UUID
    results = Patients_db.search(Query().id == patient_id)
    if not results:
        return "Patient not found", 404
    patient = results[0]

    if request.method == 'GET':
        settings = load_settings()
        departments = settings.get('departments', ["Nhi khoa", "Khám Da liễu"])
        all_services = services_table.all()
        patient_packages = patient.get('packages', [])
        # Enrich packages with status
        enriched_packages = []
        for pkg in patient_packages:
            enriched_pkg = pkg.copy()
            enriched_pkg['status'] = _package_display_status(pkg, None)  # No exam_date yet
            enriched_pkg['is_active'] = _package_is_active(pkg, None)
            enriched_packages.append(enriched_pkg)
        return render_template('new_exam.html', 
                               patient=patient, 
                               departments=departments,
                               services=all_services,
                               packages=enriched_packages)
    
    if request.method == 'POST':
        try:
            exam_date = request.form.get('exam_date')
            weight = request.form.get('weight')
            height = request.form.get('height')
            history = request.form.get('history')
            service_fee = request.form.get("service_fee")
            expected_date = request.form.get('expected_date')

            drug_names = request.form.getlist('drug_name')
            drug_quantities = request.form.getlist('drug_quantity')
            drug_notes = request.form.getlist('drug_note')
            drug_prices = request.form.getlist('drug_price')

            drugs = []
            for name, qty, note, price in zip(drug_names, drug_quantities, drug_notes, drug_prices):
                if name.strip():
                    drugs.append({
                        'name': name,
                        'quantity': qty,
                        'note': note,
                        'price': price
                    })

            patient_packages = patient.get('packages', [])
            services = _collect_services_from_form(request.form, patient_packages, exam_date)
            total_override = request.form.get('total_override')

            if request.form.get('department'):
                selected_department = request.form.get('department')
            else:
                selected_department = current_user.department if current_user.is_authenticated else 'Nhi khoa'

            computed_total = 0
            try:
                computed_total += sum(float(d.get('price',0)) * int(d.get('quantity',1)) for d in drugs)
            except Exception:
                pass
            computed_total += sum(s.get('price',0) for s in services)
            if total_override and total_override.strip():
                final_total = total_override
            else:
                final_total = computed_total

            exam_data = {
                'patient_id': patient_id,
                'exam_date': exam_date,
                'weight': weight,
                'height': height,
                'history': history,
                'service_fee': service_fee,
                'expected_date': expected_date,
                'drugs': drugs,
                'services': services,
                'paid_status' : False,
                'total_money': final_total,
                'total_override': total_override,
                'submit_time' : datetime.now().strftime('%y%m%d%H%M%S'),
                'id': str(uuid.uuid4()),
                'department': selected_department,
                'created_by_id': current_user.id if current_user.is_authenticated else None,
                'created_by_name': current_user.display_name if current_user.is_authenticated else 'Admin'
            }

            image_list = []
            images = request.files.getlist('lab_image')
            if images and images[0].filename:
                folder = _safe_patient_image_folder(patient.get('phone'))
                patient_token = _safe_filename_token(patient.get('phone'), fallback='patient')
                date_token = _safe_filename_token(exam_date, fallback='date')

                for idx, image_file in enumerate(images, start=1):
                    if image_file and image_file.filename:
                        safe_name = secure_filename(image_file.filename)
                        ext = os.path.splitext(safe_name)[1].lower()
                        if not _is_allowed_image_ext(ext):
                            return jsonify({"status": "error", "message": "Định dạng ảnh không hợp lệ"}), 400

                        new_name = f"{patient_token}_{date_token}_image_{idx}{ext}"
                        image_path = os.path.join(folder, new_name)

                        img = Image.open(image_file)
                        img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

                        buffer = io.BytesIO()
                        img.save(buffer, format=img.format or "JPEG", optimize=True, quality=85)

                        if buffer.tell() > MAX_FILE_SIZE:
                            buffer = io.BytesIO()
                            img.save(buffer, format=img.format or "JPEG", optimize=True, quality=70)

                        with open(image_path, "wb") as f:
                            f.write(buffer.getvalue())

                        image_list.append({
                            "filename": new_name,
                            "path": image_path
                        })

            if image_list:
                exam_data['images'] = image_list

            exams = patient.get("exams", [])
            exams.append(exam_data)

            update_fields = {
                "exams": exams,
                "last_visit": exam_date
            }
            if patient_packages is not None:
                update_fields["packages"] = patient_packages
            Patients_db.update(update_fields, doc_ids=[patient.doc_id])

            return jsonify({
                "status": "success",
                "message": "Dữ liệu được lưu thành công",
                "redirect_url": url_for('exam.edit_exam', exam_id=exam_data['id']),
                "exam_id": exam_data['id'],
                "patient_id": patient_id
            })
        except Exception as e:
            append_error_log(
                'Exam create failed',
                str(e),
                {
                    'route': '/exam/<patient_id>/new_exam',
                    'patient_id': patient_id,
                    'exam_date': request.form.get('exam_date'),
                }
            )
            return _json_server_error('Không thể tạo toa khám lúc này.')


    return render_template(
        'new_exam.html',
        patient=patient
    )

# NOTE: API for Generate Files
@exam_bp.route('/api/exam/generate_files', methods=['POST'])
def api_generate_files():
    try:
        data = request.get_json(silent=True) or {}
        exam_id = data.get('exam_id')
        patient_id = data.get('patient_id')
        
        if not exam_id or not patient_id:
            return jsonify({"status": "error", "message": "Missing info"}), 400

        # Find patient by UUID
        results = Patients_db.search(Query().id == patient_id)
        if not results:
            return jsonify({"status": "error", "message": "Patient not found"}), 404
        patient = results[0]
            
        exam_found = None
        for e in patient.get('exams', []):
            if e.get('id') == exam_id:
                exam_found = e
                break
                
        if not exam_found:
            return jsonify({"status": "error", "message": "Exam not found"}), 404

        # Generate
        short_exam_id = str(exam_id)[:8].replace('-','')
        department = exam_found.get('department')
        html_content = build_exam_html(patient, exam_found, doctor_name=exam_found.get('created_by_name'), department=department)
        pdf_result = generate_pdf_and_jpeg(
            html_content,
            patient.get('phone'),
            exam_found.get('exam_date'),
            short_exam_id
        )

        if pdf_result.get('success'):
            pdf_path = pdf_result.get('pdf_path')
            jpeg_path = pdf_result.get('jpeg_path')

            def to_web_path(abs_path):
                if not abs_path:
                    return None
                normalized = abs_path.replace('\\', '/')
                marker = '/files/'
                idx = normalized.lower().find(marker)
                if idx == -1:
                    return None
                return normalized[idx:]

            return jsonify({
                "status": "success",
                "success": True,
                "pdf_url": to_web_path(pdf_path),
                "jpeg_url": to_web_path(jpeg_path)
            })

        return jsonify({
            "status": "error",
            "success": False,
            "message": pdf_result.get('error', 'PDF/JPEG generation failed')
        }), 500
    except Exception as e:
        print(f"Error in /api/exam/generate_files: {e}")
        append_error_log(
            'Generate files API failed',
            str(e),
            {
                'route': '/api/exam/generate_files',
                'exam_id': data.get('exam_id') if isinstance(data, dict) else None,
                'patient_id': data.get('patient_id') if isinstance(data, dict) else None,
            }
        )
        return jsonify({
            "status": "error",
            "success": False,
            "message": "Không thể tạo file toa khám lúc này."
        }), 500


# NOTE: API for Discord
@exam_bp.route('/api/exam/send_discord', methods=['POST'])
def api_send_discord():
    data = request.json
    exam_id = data.get('exam_id')
    patient_id = data.get('patient_id')

    if not exam_id or not patient_id:
        return jsonify({"status": "error", "message": "Missing info"}), 400

    # Find patient by UUID
    results = Patients_db.search(Query().id == patient_id)
    if not results:
        return jsonify({"status": "error", "message": "Patient not found"}), 404
    patient = results[0]
        
    exam_found = None
    for e in patient.get('exams', []):
        if e.get('id') == exam_id:
            exam_found = e
            break
            
    if not exam_found:
        return jsonify({"status": "error", "message": "Exam not found"}), 404
        
    try:
        send_discord_helper(patient, exam_found)
        return jsonify({"status": "success"})
    except Exception as e:
        append_error_log(
            'Discord send failed',
            str(e),
            {
                'route': '/api/exam/send_discord',
                'patient_id': patient_id,
                'exam_id': exam_id,
            }
        )
        return _json_server_error('Không thể gửi Discord lúc này.')

# NOTE: Delete
@exam_bp.route("/exam/delete_exam/<exam_id>", methods=["POST"])
def delete_exam(exam_id):
    try:
        patient_doc_id = None
        patient_uuid = None
        patient_found = None
        patient_phone = None
        exam_date = None
        short_exam_id = str(exam_id)[:8].replace('-','')
        
        for patient in Patients_db.all():
            for exam in patient.get('exams', []):
                if exam.get('id') == exam_id:
                    patient_found = patient
                    patient_doc_id = patient.doc_id
                    patient_uuid = patient.get('id')
                    patient_phone = patient.get('phone')
                    exam_date = exam.get('exam_date')
                    break
            if patient_found:
                break
                
        if not patient_found:
            flash("some error while delete exam, please tell dev", "error")
            return jsonify({
                "status": "error",
                "message": "exam id not found"
            }), 404
                
        delete_exam_files(patient_phone, exam_date, short_exam_id)
        updated_exams = [e for e in patient_found.get('exams', []) if e['id'] != exam_id]
        Patients_db.update({'exams': updated_exams}, doc_ids=[patient_doc_id])

        return jsonify({
            "status": "success",
            "message": "Đã xóa toa thuốc",
            "redirect_url": url_for('patients.view_exams', patient_id=patient_uuid)
        })
    except Exception as e:
        append_error_log(
            'Exam delete failed',
            str(e),
            {
                'route': '/exam/delete_exam/<exam_id>',
                'exam_id': exam_id,
            }
        )
        return _json_server_error('Không thể xóa toa khám lúc này.')

# NOTE: Upload images to existing exam
@exam_bp.route('/exam/<patient_id>/<exam_id>/upload_images', methods=['POST'])
def upload_images(patient_id, exam_id):
    try:
        results = Patients_db.search(Query().id == patient_id)
        if not results:
            return jsonify({"status": "error", "message": "Patient not found"}), 404
        patient = results[0]
        
        exam_index = -1
        exams = patient.get('exams', [])
        for i, exam in enumerate(exams):
            if exam.get('id') == exam_id:
                exam_index = i
                break
                
        if exam_index == -1:
            return jsonify({"status": "error", "message": "Exam not found"}), 404

        exam_found = exams[exam_index]
        exam_date = exam_found.get('exam_date', datetime.now().strftime("%Y-%m-%d"))
        images = request.files.getlist('lab_image')
        image_list = []

        folder = _safe_patient_image_folder(patient.get('phone'))
        patient_token = _safe_filename_token(patient.get('phone'), fallback='patient')
        date_token = _safe_filename_token(exam_date, fallback='date')

        existing_images = exam_found.get('images', [])
        start_idx = len(existing_images) + 1

        for idx, image in enumerate(images, start=start_idx):
            if image and image.filename:
                safe_name = secure_filename(image.filename)
                ext = os.path.splitext(safe_name)[1].lower()
                if not _is_allowed_image_ext(ext):
                    return jsonify({"status": "error", "message": "Định dạng ảnh không hợp lệ"}), 400

                new_name = f"{patient_token}_{date_token}_image_{idx}{ext}"
                image_path = os.path.join(folder, new_name)

                img = Image.open(image)
                img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format=img.format or "JPEG", optimize=True, quality=85)
                if buffer.tell() > MAX_FILE_SIZE:
                    buffer = io.BytesIO()
                    img.save(buffer, format=img.format or "JPEG", optimize=True, quality=70)

                with open(image_path, "wb") as f:
                    f.write(buffer.getvalue())

                image_list.append({
                    "filename": new_name,
                    "path": image_path
                })

        if image_list:
            if 'images' not in exams[exam_index]:
                exams[exam_index]['images'] = []
            exams[exam_index]['images'].extend(image_list)
            Patients_db.update({'exams': exams}, doc_ids=[patient.doc_id])

        return jsonify({"status": "success", "images": image_list})
    except Exception as e:
        append_error_log(
            'Exam image upload failed',
            str(e),
            {
                'route': '/exam/<patient_id>/<exam_id>/upload_images',
                'patient_id': patient_id,
                'exam_id': exam_id,
            }
        )
        return _json_server_error('Không thể tải ảnh lên lúc này.')

# NOTE: Delete image from exam
@exam_bp.route('/exam/<patient_id>/<exam_id>/delete_image/<filename>', methods=['DELETE'])
def delete_exam_image(patient_id, exam_id, filename):
    try:
        safe_route_filename = secure_filename(filename)
        if not safe_route_filename or safe_route_filename != filename:
            return jsonify({"status": "error", "message": "Invalid filename"}), 400

        results = Patients_db.search(Query().id == patient_id)
        if not results:
            return jsonify({"status": "error", "message": "Patient not found"}), 404
        patient = results[0]
        
        exam_index = -1
        exams = patient.get('exams', [])
        for i, exam in enumerate(exams):
            if exam.get('id') == exam_id:
                exam_index = i
                break
        
        if exam_index == -1:
            return jsonify({"status": "error", "message": "Exam not found"}), 404
        
        current_images = exams[exam_index].get('images', [])
        image_to_remove = None
        for img in current_images:
            if img.get('filename') == safe_route_filename:
                image_to_remove = img
                break
        
        if not image_to_remove:
            return jsonify({"status": "error", "message": "Image not found in exam"}), 404
        
        new_images = [img for img in current_images if img.get('filename') != safe_route_filename]
        exams[exam_index]['images'] = new_images
        
        try:
            patient_folder = _safe_patient_image_folder(patient.get('phone'))
            candidate_path = os.path.abspath(os.path.join(patient_folder, safe_route_filename))
            patient_folder_abs = os.path.abspath(patient_folder)
            if not (candidate_path == patient_folder_abs or candidate_path.startswith(patient_folder_abs + os.sep)):
                return jsonify({"status": "error", "message": "Invalid file path"}), 400

            if os.path.exists(candidate_path):
                os.remove(candidate_path)
            else:
                 print(f"File not found on disk: {candidate_path}")
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        Patients_db.update({'exams': exams}, doc_ids=[patient.doc_id])
        
        return jsonify({"status": "success", "message": "Image deleted"})
    except Exception as e:
        append_error_log(
            'Exam image delete failed',
            str(e),
            {
                'route': '/exam/<patient_id>/<exam_id>/delete_image/<filename>',
                'patient_id': patient_id,
                'exam_id': exam_id,
                'filename': safe_route_filename if 'safe_route_filename' in locals() else filename,
            }
        )
        return _json_server_error('Không thể xóa ảnh lúc này.')
