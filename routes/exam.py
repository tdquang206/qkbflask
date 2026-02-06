from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort, flash
from datetime import datetime
from tinydb import Query
import uuid
from werkzeug.utils import secure_filename
import os, io, json
from PIL import Image
import requests

from utils.pdf_generator import generate_exam_file_name, build_exam_html, generate_pdf_and_jpeg, delete_exam_files

exam_bp = Blueprint('exam', __name__)
from shared_db import db, patients_table as Patients_db

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

    # Build Message based on settings
    fields = []
    
    if settings.get('include_date'):
        fields.append(f"**Ngày khám:** {exam_data.get('exam_date')}")
    
    if settings.get('include_kid_name'):
        fields.append(f"**Bé:** {patient.get('kid_name')} ({patient.get('kid_birthday')})")
        
    if settings.get('include_parent_name'):
        fields.append(f"**Phụ huynh:** {patient.get('name')}")
        
    if settings.get('include_phone'):
        fields.append(f"**SĐT:** {patient.get('phone')}")
        
    if settings.get('include_address'):
        fields.append(f"**Địa chỉ:** {patient.get('address')}")
        
    if settings.get('include_total_money'):
        fields.append(f"**Tổng tiền:** {exam_data.get('total_money')}")

    message_content = "\n".join(fields)
    
    if settings.get('include_table'):
        # Build text table
        table_str = "```\n"
        table_str += f"{'Tên thuốc':<20} | {'SL':<5} | {'Ghi chú'}\n"
        table_str += "-"*40 + "\n"
        for drug in exam_data.get('drugs', []):
            name = drug.get('name', '')[:20]
            qty = str(drug.get('quantity', ''))
            note = drug.get('note', '')
            table_str += f"{name:<20} | {qty:<5} | {note}\n"
        table_str += "```"
        message_content += "\n\n**Toa thuốc:**\n" + table_str

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
    
    
    for patient in Patients_db.all():
        for exam in patient.get('exams', []):
            if exam.get('id') == exam_id:
                exam_editting = exam
                patient_found = patient
                break
    if not exam_editting or not patient_found:
        flash("Unknown exam info", "error")
        return redirect(url_for('patient.view_patients'))
    
    if request.method == 'GET':
        return render_template('edit_exam.html', patient = patient_found, exam=exam_editting)

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

        # prepair exam data
        exam_data = {
            'patient_id': patient_found.doc_id,
            'exam_date': exam_date,
            'weight': weight,
            'height': height,
            'history': history,
            'service_fee': service_fee,
            'expected_date': expected_date,
            'drugs': drugs,
            'paid_status' : False,
            'total_money': total_money,
            # get submit time # YYMMDDHHMMSS
            'submit_time' : datetime.now().strftime('%y%m%d%H%M%S'),
            'id': exam_id
            
        }
        print(exam_data)
        
        
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
        Patients_db.update({"exams": exams, "last_visit": exam_date}, doc_ids=[patient_found.doc_id])
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
          "patient_id": patient_found.doc_id
        })

# NOTE: Create
# Create new exam
@exam_bp.route('/exam/<int:patient_id>/new_exam', methods=['GET', 'POST'])
def new_exam(patient_id):

    patient = Patients_db.get(doc_id = patient_id)

    if request.method == 'GET':
        return render_template('new_exam.html', patient = patient)
    
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
        # prepair exam data
        exam_data = {
            'patient_id': patient_id,
            'exam_date': exam_date,
            'weight': weight,
            'height': height,
            'history': history,
            'service_fee': service_fee,
            'expected_date': expected_date,
            'drugs': drugs,
            'paid_status' : False,
            'total_money': total_money,
            # get submit time # YYMMDDHHMMSS
            'submit_time' : datetime.now().strftime('%y%m%d%H%M%S'),
            'id': str(uuid.uuid4())
            
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
        Patients_db.update({
            "exams": exams,
            "last_visit": exam_date
            }, 
            doc_ids=[patient_id])

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

    patient = Patients_db.get(doc_id=int(patient_id))
    if not patient:
        return jsonify({"status": "error", "message": "Patient not found"}), 404
        
    exam_found = None
    for e in patient.get('exams', []):
        if e.get('id') == exam_id:
            exam_found = e
            break
            
    if not exam_found:
        return jsonify({"status": "error", "message": "Exam not found"}), 404

    # Generate
    short_exam_id = str(exam_id)[:8].replace('-','')
    html_content = build_exam_html(patient, exam_found)
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

    patient = Patients_db.get(doc_id=int(patient_id))
    if not patient:
        return jsonify({"status": "error", "message": "Patient not found"}), 404
        
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
                    patient_phone = patient.get('phone')
                    exam_date = exam.get('exam_date')
                    break
            if exam_will_be_deleted:
                    break
        if not exam_will_be_deleted:
            flash("some error while delete exam, please tell dev", "error")
            return jsonify({
                "status": "error",
                "message": "exam id not found"
            }), 404
                
        # ✅ Delete PDF/JPEG files
        deleted_files = delete_exam_files(patient_phone, exam_date, short_exam_id)

        # delete from database
        updated_exams = [e for e in patient.get('exams', []) if e['id'] != exam_id]
        Patients_db.update({'exams': updated_exams}, doc_ids=[patient_doc_id])

        return jsonify({
            "status": "success",
            "message": "Đã xóa toa thuốc",
            "redirect_url": url_for('view_exams', patient_id=patient_doc_id)
        })

@exam_bp.route('/exam/<int:patient_id>/upload_images', methods=['POST'])
def upload_images(patient_id):
    patient = Patients_db.get(doc_id=patient_id)
    exam_date = datetime.now().strftime("%Y-%m-%d")

    images = request.files.getlist('lab_images')
    image_list = []

    folder = os.path.join('uploads', 'patient_image', patient.get('phone'))
    os.makedirs(folder, exist_ok=True)

    for idx, image in enumerate(images, start=1):
        if image and image.filename:
            safe_name = secure_filename(image.filename)
            ext = os.path.splitext(safe_name)[1].lower()
            new_name = f"{patient.get('phone')}_{exam_date}_image_{idx}{ext}"
            image_path = os.path.join(folder, new_name)

            # Resize with Pillow
            img = Image.open(image)
            img.thumbnail((2000, 2000), Image.ANTIALIAS)

            buffer = io.BytesIO()
            img.save(buffer, format=img.format or "JPEG", optimize=True, quality=85)
            if buffer.tell() > 1 * 1024 * 1024:  # >1MB
                buffer = io.BytesIO()
                img.save(buffer, format=img.format or "JPEG", optimize=True, quality=70)

            with open(image_path, "wb") as f:
                f.write(buffer.getvalue())

            # Return URL for frontend thumbnail
            image_list.append({
                "filename": new_name,
                "url": f"/{image_path}"  # adjust if you serve uploads differently
            })

    return jsonify({"status": "success", "images": image_list})
