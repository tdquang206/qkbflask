from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort, flash
from datetime import datetime
from tinydb import TinyDB, Query
import uuid
from werkzeug.utils import secure_filename
import os

from utils.pdf_generator import generate_exam_file_name, build_exam_html, generate_pdf_and_jpeg, delete_exam_files

exam_bp = Blueprint('exam', __name__)
db = TinyDB('db.json', encoding='utf-8')
Patients_db = db.table('patients')

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
        # print(f'exam id {exam_editting}')
        # print(f'patient id {patient_found}')
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
                exams[i].update(exam_data)
                updated=True
                break

        # if exam_id change: create a new one
        if not updated:
            exams.append(exam_data)

        # Update the patient document in TinyDB
        Patients_db.update({"exams": exams, "last_visit": exam_date}, doc_ids=[patient_found.doc_id])
        # NOTE: PDF and JPEG files, overwrite old files
        html_content = build_exam_html(patient_found, exam_data)
        pdf_result = generate_pdf_and_jpeg(
            html_content,
            patient_found.get("phone"),
            exam_date,
            exam_id
        )

        return jsonify({
          "status": "success",
          "message": "Exam updated"  
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
        image = request.files.get('lab_image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join('uploads', filename)  # Changed to direct path
            image.save(image_path)
            exam_data['image_path'] = image_path
            
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
        
        html_content = build_exam_html(patient, exam_data)
        pdf_result = generate_pdf_and_jpeg(
            html_content,
            patient.get('phone'),
            exam_date,
            short_exam_id
        )

        return jsonify({
            "status": "success",
            "message": "Dữ liệu được lưu thành công",
            "redirect_url": url_for('exam.edit_exam', exam_id=exam_data['id'])
        })


    return render_template(
        'new_exam.html',
        patient=patient
    )

# NOTE: Delete
@exam_bp.route("/exam/delete_exam/<exam_id>", methods=["POST"])
def delete_exam(exam_id):

    if request.method == 'POST':
        exam_will_be_deleted = None
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