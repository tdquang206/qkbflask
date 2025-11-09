from flask import Flask, render_template, request, redirect, url_for, jsonify, Blueprint
from tinydb import TinyDB, Query, where
from werkzeug.utils import secure_filename
from datetime import datetime
from collections import defaultdict
import os
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

db = TinyDB('db.json', encoding='utf-8')
patients = db.table('patients')
drugs = db.table('drugs')
exams = db.table('exams')

# include blueprint
from routes.mua_thuoc import mua_thuoc_bp
app.register_blueprint(mua_thuoc_bp)

from routes.route_all_exams_page import exams_list_bp
app.register_blueprint(exams_list_bp)

from routes.exam import exam_bp
app.register_blueprint(exam_bp)

@app.route('/')
def index():
    return render_template('index.html')


# drugs: view, edit, delete
Drug = Query()
@app.route('/drugs', methods=['GET', 'POST'])
def manage_drugs():
    if request.method == 'POST':
        drugs.insert({
            'sku': request.form['sku'],
            'name': request.form['name'],
            'sell_price': float(request.form.get('sell_price', 0)) if request.form.get('sell_price', '').isdigit() else "",
            'buy_price': float(request.form.get('buy_price', 0)) if request.form.get('buy_price', '').isdigit() else "",
            'quantity': int(request.form.get('quantity', 0)) if request.form.get('quantity', '').isdigit() else "",
            'inventory': int(request.form.get('inventory', 0)) if request.form.get('inventory', '').isdigit() else ""
        })
        return redirect(url_for('manage_drugs'))
    
    return render_template('drugs.html', drugs=drugs.all())

@app.route('/edit_drug/<int:drug_id>', methods=['GET', 'POST'])
def edit_drug(drug_id):
    drug = drugs.get(doc_id=drug_id)
    if request.method == 'POST':
        drugs.update({
            'sku': request.form['sku'],
            'name': request.form['name'],
            'sell_price': float(request.form.get('sell_price', 0)) if request.form.get('sell_price', '').isdigit() else "",
            'buy_price': float(request.form.get('buy_price', 0)) if request.form.get('buy_price', '').isdigit() else "",
            'quantity': int(request.form.get('quantity', 0)) if request.form.get('quantity', '').isdigit() else "",
            'inventory': int(request.form.get('inventory', 0)) if request.form.get('inventory', '').isdigit() else ""
        }, doc_ids=[drug_id])
        return redirect(url_for('manage_drugs'))
    return render_template('edit_drug.html', drug=drug)

@app.route('/delete_drug/<int:drug_id>')
def delete_drug(drug_id):
    drugs.remove(doc_ids=[drug_id])
    return redirect(url_for('manage_drugs'))

# get drugs list by ajax
@app.route('/api/drugs')
def api_drugs():
    return jsonify(drugs.all())

# Patients
Patients = Query()
@app.route('/patients', methods=['GET', 'POST'])
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
        return redirect(url_for('manage_patients'))
    return render_template('patients.html', patients=patients.all())

@app.route('/patient/<int:patient_id>')
def exam_patient(patient_id):
    patient = patients.get(doc_id=patient_id)
    if not patient:
        return "Lỗi kết nối /patient/<int: patient_id>"
    # Later: redirect to exam screen
    return render_template('exam.html', patient=patient)
    

# edit patients info
@app.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('manage_patients'))
    return render_template('edit_patient.html', patient=patient)

@app.route('/add_patient', methods=['GET', 'POST'])
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
        return redirect(url_for('manage_patients'))
    return render_template('add_patient.html')

@app.route('/patient/<int:patient_id>/exams')
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
    
@app.route('/drug_sold')
def drug_sold():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Parse dates if provided
    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    # Aggregate drug quantities
    totals = defaultdict(int)
    for exam in exams.all():
        try:
            exam_date = datetime.strptime(exam.get('exam_date', ''), "%Y-%m-%d")
        except Exception:
            continue

        if start and exam_date < start:
            continue
        if end and exam_date > end:
            continue

        for drug in exam.get('drugs', []):
            qty = int(drug.get('quantity', 0) or 0)
            totals[drug.get('name', 'Unknown')] += qty

    # Convert to list of dicts for template
    drug_totals = [{"name": name, "quantity": qty} for name, qty in totals.items()]

    return render_template(
        'drug_sold.html',
        drug_totals=drug_totals,
        start_date=start_date,
        end_date=end_date
    )




@app.route('/exams')
def all_exams():
    return render_template('exams.html', exams=exams.all(), patients=patients)

if __name__ == '__main__':
    app.run(debug=True)