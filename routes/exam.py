from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from tinydb import TinyDB, Query
import uuid
from werkzeug.utils import secure_filename
import os

exam_bp = Blueprint('exam', __name__)
db = TinyDB('db.json')
Patients_db = db.table('patients')

# NOTE: Read and Edit CRUD code
@exam_bp.route("/exam/<int:patient_id>/edit_exam/<exam_id>", methods=['POST', 'GET'])
def edit_exam(patient_id, exam_id):
    patient = Patients_db.get(doc_id=patient_id)
    if not patient:
        return "Patient not found", 404
    
    # Find exam in patient's exams list by matching id
    exam = next((e for e in patient.get('exams', []) if e.get('id') == exam_id), None) 
    if not exam:
        abort(404)
    # Print for debugging
    print(f"Found exam: {exam}")
    
    if request.method == 'GET':
        return render_template('edit_exam.html', patient=patient, exam=exam)

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
            'id': exam_id
            
        }
        
        
        # Handle image upload if present
        image = request.files.get('lab_image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join('uploads', filename)  # Changed to direct path
            image.save(image_path)
            exam_data['image_path'] = image_path
            
        # search the exam id
        exams = patient.get("exams", [])
        updated = False
        for i, exam in enumerate(exams):
            if exam.get('id') == exam_id:
                exams[i] = exam_data
                updated=True
                break

        # if exam_id change: create a new one
            if not updated:
                exams.append(exam_data)

        # Update the patient document in TinyDB
        Patients_db.update({"exams": exams}, doc_ids=[patient_id])

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
        Patients_db.update({"exams": exams}, doc_ids=[patient_id])

        return jsonify({
            "status": "success",
            "message": "Dữ liệu được lưu thành công",
            "redirect_url": url_for('exam.edit_exam', patient_id=patient_id, exam_id=exam_data['id'])
        })


    return render_template(
        'new_exam.html',
        patient=patient
    )

# NOTE: Delete
@exam_bp.route("/exam/<int:patient_id>/delete_exam/<exam_id>", methods=["POST"])
def delete_exam(patient_id, exam_id):

    if request.method == 'POST':
        patient = Patients_db.get(doc_id=patient_id)
        if not patient:
            return "Patient not found", 404
        
        exams = patient.get('exams', [])

        updated_exams = [e for e in exams if e['id'] != exam_id]

        if len(exams) == len(updated_exams):
            return "Not found exam_id", 404

        Patients_db.update({'exams': updated_exams}, doc_ids=[patient_id])

        return jsonify({
            "status": "success",
            "message": "Đã xóa toa thuốc",
            "redirect_url": url_for('view_exams', patient_id=patient_id)
        })