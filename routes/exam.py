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

exam_bp = Blueprint('exam', __name__)
from shared_db import db, patients_table as Patients_db, services_table

# for image
MAX_SIZE = (2000, 2000)
MAX_FILE_SIZE = 1 * 1024 * 1024
SETTINGS_FILE = 'user_settings.json'

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
        return render_template('edit_exam.html', 
            patient=patient_found, 
            exam=exam_editting, 
            departments=departments,
            services=all_services,
            packages=patient_packages)

    if request.method == 'POST':
        # data
        exam_date = request.form.get('exam_date')
        weight = request.form.get('weight')
        height = request.form.get('height')
        history = request.form.get('history')
        # string, e.g. "50000"
        service_fee = request.form.get("service_fee")  
        
        expected_date = request.form.get('expected_date')

        # Collect drug rows (they come as lists)
        drug_names = request.form.getlist('drug_name')
        drug_quantities = request.form.getlist('drug_quantity')
        drug_notes = request.form.getlist('drug_note')
        drug_prices = request.form.getlist('drug_price')
        total_money = request.form.get('total_money') 
        send_discord_flag = request.form.get('send_discord')

        # try to discard empty name when receiving data
        drugs = []
        for name, qty, note, price in zip(drug_names, drug_quantities, drug_notes, drug_prices):
            if name.strip():
                drugs.append({
                    'name': name,
                    'quantity': qty,
                    'note': note,
                    'price': price
                })

        # --- new: handle selected services and packages ---
        service_ids = request.form.getlist('service_id')
        service_names = request.form.getlist('service_name')
        service_prices = request.form.getlist('service_price')
        services = []
        # load patient packages for analysis
        patient_packages = patient_found.get('packages', [])
        for sid, nm, pr in zip(service_ids, service_names, service_prices):
            if not sid:
                continue
            price_val = float(pr or 0)
            # apply package discount if available
            for pkg in patient_packages:
                if pkg.get('service_id') == sid and pkg.get('remaining_sessions', 0) > 0:
                    # charge package unit price instead
                    price_val = pkg.get('unit_price', price_val)
                    pkg['remaining_sessions'] = pkg.get('remaining_sessions', 0) - 1
                    break
            services.append({'id': sid, 'name': nm, 'price': price_val})

        # total override (manual edit by doctor)
        total_override = request.form.get('total_override')

        # calculate total_money if override not provided
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
            'patient_id': patient_found.get('id'), # Use UUID
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
            # get submit time # YYMMDDHHMMSS
            'submit_time' : datetime.now().strftime('%y%m%d%H%M%S'),
            'id': exam_id,
            # Preserve existing creator info (use admin tool to change doctor/department)
            'department': exam_editting.get('department', 'Nhi khoa'),
            'created_by_id': exam_editting.get('created_by_id'),
            'created_by_name': exam_editting.get('created_by_name', 'Admin')
        }

        # if we modified packages, save back to patient record
        if patient_packages != patient_found.get('packages', []):
            patient_found['packages'] = patient_packages

        # print(exam_data)
        
        
        # Handle image upload if present
        image = request.files.get('lab_image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join('uploads', filename)  # Changed to direct path
            image.save(image_path)
            exam_data['image_path'] = image_path
            
        # search the exam id
        exams = patient_found.get("exams", [])
        updated = False
        for i, exam in enumerate(exams):
            if exam.get('id') == exam_id:
                # get old exam_id
                old_date = exam.get('exam_date')
                short_id = str(exam_id)[:8].replace('-','')
                # delete old physical pdf and jpeg files
                if old_date:
                    delete_exam_files(patient_found.get('phone'), old_date, short_id)
                # update newdata
                exams[i].update(exam_data)
                updated = True
                break

        # if exam_id change: create a new one
        if not updated:
            exams.append(exam_data)

        # Update the patient document in TinyDB
        # We must use doc_ids to update specific record found by earlier iteration
        update_fields = {"exams": exams, "last_visit": exam_date}
        # if packages changed, persist them too
        if patient_packages is not None:
            update_fields["packages"] = patient_packages
        Patients_db.update(update_fields, doc_ids=[patient_found.doc_id])
        # NOTE: PDF and JPEG files, overwrite old files
        short_exam_id = str(exam_id)[:8].replace('-','')
        # html_content = build_exam_html(patient_found, exam_data)
        # pdf_result = generate_pdf_and_jpeg(
        #     html_content,
        #     patient_found.get("phone"),
        #     exam_date,
        #     short_exam_id
        # )

        if send_discord_flag:
            # We will send discord in a separate request
            pass

        return jsonify({
          "status": "success",
          "message": "Exam updated",
          "exam_id": exam_data['id'],
          "patient_id": patient_found.get('id') # UUID
        })

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
        return render_template('new_exam.html', 
                               patient=patient, 
                               departments=departments,
                               services=all_services,
                               packages=patient_packages)
    
    if request.method == 'POST':
        # data
        exam_date = request.form.get('exam_date')
        weight = request.form.get('weight')
        height = request.form.get('height')
        history = request.form.get('history')
        # string, e.g. "50000"
        service_fee = request.form.get("service_fee")  
        
        expected_date = request.form.get('expected_date')

        # Collect drug rows (they come as lists)
        drug_names = request.form.getlist('drug_name')
        drug_quantities = request.form.getlist('drug_quantity')
        drug_notes = request.form.getlist('drug_note')
        drug_prices = request.form.getlist('drug_price')
        total_money = request.form.get('total_money') 
        send_discord_flag = request.form.get('send_discord')

        # try to discard empty name when receiving data
        drugs = []
        for name, qty, note, price in zip(drug_names, drug_quantities, drug_notes, drug_prices):
            if name.strip():
                drugs.append({
                    'name': name,
                    'quantity': qty,
                    'note': note,
                    'price': price
                })

        # handle services & packages
        service_ids = request.form.getlist('service_id')
        service_names = request.form.getlist('service_name')
        service_prices = request.form.getlist('service_price')
        services = []
        patient_packages = patient.get('packages', [])
        for sid, nm, pr in zip(service_ids, service_names, service_prices):
            if not sid:
                continue
            price_val = float(pr or 0)
            for pkg in patient_packages:
                if pkg.get('service_id') == sid and pkg.get('remaining_sessions', 0) > 0:
                    price_val = pkg.get('unit_price', price_val)
                    pkg['remaining_sessions'] = pkg.get('remaining_sessions', 0) - 1
                    break
            services.append({'id': sid, 'name': nm, 'price': price_val})

        total_override = request.form.get('total_override')

        # prepair exam data
        if request.form.get('department'):
            selected_department = request.form.get('department')
        else:
            selected_department = current_user.department if current_user.is_authenticated else 'Nhi khoa'

        # compute totals
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
            'patient_id': patient_id, # UUID
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
            # get submit time # YYMMDDHHMMSS
            'submit_time' : datetime.now().strftime('%y%m%d%H%M%S'),
            'id': str(uuid.uuid4()),
            'department': selected_department,
            'created_by_id': current_user.id if current_user.is_authenticated else None,
            'created_by_name': current_user.display_name if current_user.is_authenticated else 'Admin'
        }
        short_exam_id = str(exam_data['id'])[:8].replace('-','')
        # Handle image upload if present
        image_list = []
        images = request.files.getlist('lab_image')

        if images and images[0].filename:
            folder = os.path.join('uploads', 'patient_image', patient.get('phone'))
            os.makedirs(folder, exist_ok=True)
            folder = os.path.join('uploads', 'patient_image', patient.get('phone'))
            os.makedirs(folder, exist_ok=True)

            for idx, image_file in enumerate(images, start=1):
                # ✅ Renamed loop variable to 'image_file' to avoid conflict
                if image_file and image_file.filename:
                    safe_name = secure_filename(image_file.filename)
                    ext = os.path.splitext(safe_name)[1].lower()
                    new_name = f"{patient.get('phone')}_{exam_date}_image_{idx}{ext}"
                    image_path = os.path.join(folder, new_name)

                    # Resize
                    img = Image.open(image_file)
                    img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
                    
                    # Save to buffer to check size
                    buffer = io.BytesIO()
                    img.save(buffer, format=img.format or "JPEG", optimize=True, quality=85)
                    
                    # If too large, reduce quality
                    if buffer.tell() > MAX_FILE_SIZE:
                        buffer = io.BytesIO()
                        img.save(buffer, format=img.format or "JPEG", optimize=True, quality=70)
                    
                    # Write to disk
                    with open(image_path, "wb") as f:
                        f.write(buffer.getvalue())
                    
                    image_list.append({
                        "filename": new_name,
                        "path": image_path
                    })
        
        if image_list:    
            exam_data['images'] = image_list
            
        # Append to patient's exams list
        exams = patient.get("exams", [])
        exams.append(exam_data)

        # Update the patient document in TinyDB
        # Use doc_ids here because we already found the patient object and its doc_id
        update_fields = {
            "exams": exams,
            "last_visit": exam_date
        }
        # persist package changes too
        if patient_packages is not None:
            update_fields["packages"] = patient_packages
        Patients_db.update(update_fields, doc_ids=[patient.doc_id])

        # NOTE: create PDF and JPEG files
        
        # html_content = build_exam_html(patient, exam_data)
        # pdf_result = generate_pdf_and_jpeg(
        #     html_content,
        #     patient.get('phone'),
        #     exam_date,
        #     short_exam_id
        # )

        # if send_discord_flag:
        #     send_discord_helper(patient, exam_data)

        return jsonify({
            "status": "success",
            "message": "Dữ liệu được lưu thành công",
            "redirect_url": url_for('exam.edit_exam', exam_id=exam_data['id']),
            "exam_id": exam_data['id'],
            "patient_id": patient_id
        })


    return render_template(
        'new_exam.html',
        patient=patient
    )

# NOTE: API for Generate Files
@exam_bp.route('/api/exam/generate_files', methods=['POST'])
def api_generate_files():
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
         return jsonify({"status": "success"})
    else:
         return jsonify({"status": "error", "message": pdf_result.get('error')}), 500


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
        return jsonify({"status": "error", "message": str(e)}), 500

# NOTE: Delete
@exam_bp.route("/exam/delete_exam/<exam_id>", methods=["POST"])
def delete_exam(exam_id):

        patient_doc_id = None
        patient_uuid = None
        # data for pdf filename
        patient_found = None
        patient_phone = None
        exam_date = None
        short_exam_id = str(exam_id)[:8].replace('-','')
        
        for patient in Patients_db.all():
            for exam in patient.get('exams', []):
                if exam.get('id') == exam_id:
                    exam_will_be_deleted = exam
                    patient_found = patient
                    patient_doc_id = patient.doc_id
                    patient_uuid = patient.get('id')
                    patient_phone = patient.get('phone')
                    exam_date = exam.get('exam_date')
                    break
            if patient_found: # Optimized break
                break
                
        if not patient_found:
            flash("some error while delete exam, please tell dev", "error")
            return jsonify({
                "status": "error",
                "message": "exam id not found"
            }), 404
                
        # ✅ Delete PDF/JPEG files
        deleted_files = delete_exam_files(patient_phone, exam_date, short_exam_id)

        # delete from database
        updated_exams = [e for e in patient_found.get('exams', []) if e['id'] != exam_id]
        Patients_db.update({'exams': updated_exams}, doc_ids=[patient_doc_id])

        return jsonify({
            "status": "success",
            "message": "Đã xóa toa thuốc",
            # "redirect_url": url_for('view_exams', patient_id=patient_doc_id) # Was wrong?
            "redirect_url": url_for('patients.view_exams', patient_id=patient_uuid)
        })

# NOTE: Upload images to existing exam
@exam_bp.route('/exam/<patient_id>/<exam_id>/upload_images', methods=['POST'])
def upload_images(patient_id, exam_id):
    # Find patient by UUID
    results = Patients_db.search(Query().id == patient_id)
    if not results:
        return jsonify({"status": "error", "message": "Patient not found"}), 404
    patient = results[0]
    
    # Find the exam index
    exam_index = -1
    exams = patient.get('exams', [])
    for i, exam in enumerate(exams):
        if exam.get('id') == exam_id:
            exam_index = i
            break
            
    if exam_index == -1:
        return jsonify({"status": "error", "message": "Exam not found"}), 404

    exam_found = exams[exam_index]
    
    # Get exam date for filename
    exam_date = exam_found.get('exam_date', datetime.now().strftime("%Y-%m-%d"))

    images = request.files.getlist('lab_image')
    image_list = []

    folder = os.path.join('uploads', 'patient_image', patient.get('phone'))
    os.makedirs(folder, exist_ok=True)

    # Get existing image count to continue numbering
    existing_images = exam_found.get('images', [])
    start_idx = len(existing_images) + 1

    for idx, image in enumerate(images, start=start_idx):
        if image and image.filename:
            safe_name = secure_filename(image.filename)
            ext = os.path.splitext(safe_name)[1].lower()
            new_name = f"{patient.get('phone')}_{exam_date}_image_{idx}{ext}"
            image_path = os.path.join(folder, new_name)

            # Resize with Pillow
            img = Image.open(image)
            img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format=img.format or "JPEG", optimize=True, quality=85)
            if buffer.tell() > MAX_FILE_SIZE:  # >1MB
                buffer = io.BytesIO()
                img.save(buffer, format=img.format or "JPEG", optimize=True, quality=70)

            with open(image_path, "wb") as f:
                f.write(buffer.getvalue())

            # Add to image list
            image_list.append({
                "filename": new_name,
                "path": image_path
            })

    # Update exam with new images
    if image_list:
        if 'images' not in exams[exam_index]:
            exams[exam_index]['images'] = []
        exams[exam_index]['images'].extend(image_list)
        
        # Update the patient document in TinyDB with explicit exams list
        Patients_db.update({'exams': exams}, doc_ids=[patient.doc_id])

    return jsonify({"status": "success", "images": image_list})

# NOTE: Delete image from exam
@exam_bp.route('/exam/<patient_id>/<exam_id>/delete_image/<filename>', methods=['DELETE'])
def delete_exam_image(patient_id, exam_id, filename):
    # Find patient by UUID
    results = Patients_db.search(Query().id == patient_id)
    if not results:
        return jsonify({"status": "error", "message": "Patient not found"}), 404
    patient = results[0]
    
    # Find the exam index
    exam_index = -1
    exams = patient.get('exams', [])
    for i, exam in enumerate(exams):
        if exam.get('id') == exam_id:
            exam_index = i
            break
    
    if exam_index == -1:
        return jsonify({"status": "error", "message": "Exam not found"}), 404
    
    # Get current images
    current_images = exams[exam_index].get('images', [])
    
    # Find image to remove
    image_to_remove = None
    for img in current_images:
        if img.get('filename') == filename:
            image_to_remove = img
            break
    
    if not image_to_remove:
        return jsonify({"status": "error", "message": "Image not found in exam"}), 404
    
    # Remove image from list
    new_images = [img for img in current_images if img.get('filename') != filename]
    exams[exam_index]['images'] = new_images
    
    # Delete physical file
    try:
        if os.path.exists(image_to_remove['path']):
            os.remove(image_to_remove['path'])
        else:
             print(f"File not found on disk: {image_to_remove['path']}")
    except Exception as e:
        print(f"Error deleting file: {e}")
    
    # Update database with explicit exams list
    Patients_db.update({'exams': exams}, doc_ids=[patient.doc_id])
    
    return jsonify({"status": "success", "message": "Image deleted"})
