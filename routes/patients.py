from flask import Blueprint, render_template, request, redirect, url_for
from tinydb import Query
from shared_db import patients_table as patients

patients_bp = Blueprint('patients', __name__)

# Patients
Patients = Query()

@patients_bp.route('/patients', methods=['GET', 'POST'])
def manage_patients():
    if request.method == 'POST':
        kid_name = request.form.get('kid_name', '')
        kid_birthdate = request.form.get('kid_birthdate', '')
        name = request.form.get('name', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')

        # put to database
        patients.insert({
            'kid_name' : kid_name, 
            'kid_birthday' : kid_birthdate,
            'name': name, 
            'phone': phone, 
            'address': address,
            'last_visit': '',
            'exams': []   # <-- always add this!
        })
        return redirect(url_for('patients.manage_patients'))
    return render_template('patients.html', patients=patients.all())

@patients_bp.route('/patient/<int:patient_id>')
def exam_patient(patient_id):
    patient = patients.get(doc_id=patient_id)
    if not patient:
        return "Lỗi kết nối /patient/<int: patient_id>"
    # Later: redirect to exam screen
    return render_template('exam.html', patient=patient)
    

# edit patients info
@patients_bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    patient = patients.get(doc_id=patient_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update':
            patients.update({
                'kid_name': request.form.get('kid_name', ''),
                'kid_birthday': request.form.get('kid_birthday', ''),
                'name': request.form.get('name', ''),
                'phone': request.form.get('phone', ''),
                'address': request.form.get('address', '')
            }, doc_ids=[patient_id])
        elif action == 'delete':
            patients.remove(doc_ids=[patient_id])
        return redirect(url_for('patients.manage_patients'))
    return render_template('edit_patient.html', patient=patient)

@patients_bp.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        kid_name = request.form.get('kid_name', '')
        kid_birthday = request.form.get('kid_birthday', '')
        name = request.form.get('name', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        patients.insert({
            'kid_name': kid_name,
            'kid_birthday': kid_birthday,
            'name': name,
            'phone': phone,
            'address': address,
            'last_visit': '',
            'exams': []   # <-- always add this!
        })
        return redirect(url_for('patients.manage_patients'))
    return render_template('add_patient.html')

@patients_bp.route('/patient/<int:patient_id>/exams')
def view_exams(patient_id):
    Patient = Query()
    patient = patients.get(doc_id=patient_id)
    if not patient:
        return "Patient not found", 404

    # Get all exams for this patient
    patient_exams = patient.get("exams", [])

    # patient_exams = exams.search(Query().patient_id == patient_id)
    
    def exam_sort_key(e):
        return (
            e.get('exam_date', ''),
            e.get('submit_time', '')
        )
    patient_exams = sorted(patient_exams, key=exam_sort_key, reverse=True)

    # Render the renamed template
    return render_template('previous_exams.html', patient=patient, exams=patient_exams)
