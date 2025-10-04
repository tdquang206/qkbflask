from flask import Flask, render_template, request, redirect, url_for, jsonify
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
            'sell_price': float(request.form['sell_price']),
            'buy_price': float(request.form['buy_price']),
            'quantity': int(request.form['quantity']),
            'inventory': int(request.form['inventory']) if request.form['inventory'].isdigit() else ""
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
            'sell_price': float(request.form['sell_price']),
            'buy_price': float(request.form['buy_price']),
            'quantity': int(request.form['quantity']),
            'inventory': request.form['inventory']
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
            'last_visit': ''})
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
            'last_visit': ''
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
    patient_exams = exams.search(Query().patient_id == patient_id)

    # Render the renamed template
    return render_template('previous_exams.html', patient=patient, exams=patient_exams)



@app.route('/exam/<int:patient_id>', methods=['GET', 'POST'])
def exam(patient_id):
    Patient = Query()
    patient = patients.get(doc_id=patient_id)
    
    if request.method == 'POST':
        # save state or not
        state = reques.form.get('mode')
        # data
        exam_date = request.form.get('exam_date')
        weight = request.form.get('weight')
        height = request.form.get('height')
        history = request.form.get('history')
        expected_date = request.form.get('expected_date')

        # Collect drug rows (they come as lists)
        drug_names = request.form.getlist('drug_name')
        drug_quantities = request.form.getlist('drug_quantity')
        drug_notes = request.form.getlist('drug_note')
        drug_prices = request.form.getlist('drug_price')

        # try to discard empty name when receiving data
        drugs = []
        for name, qty, note, price in zip(drug_names, drug_quantities, drug_notes, drug_prices):
            if name.strip():
                drugs.append({
                    'name': drug_names[i],
                    'quantity': drug_quantities[i],
                    'note': drug_notes[i],
                    'price': drug_prices[i]
                })

        # exam data to POST
        exam_data = {
            'patient_id': patient_id,
            'exam_date': exam_date,
            'weight': weight,
            'height': height,
            'history': history,
            'expected_date': expected_date,
            'drugs': drugs
        }
        
        
        # image path
        image = request.files.get('lab_image')
        image_path = ''

        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
        # save or update if state = reques.form.get('mode') == 'save'
        if state == 'save':   
            # exams.insert({
            #     'patient_id': patient_id,
            #     'exam_date': exam_date,
            #     'weight': weight,
            #     'height': height,
            #     'history': history,
            #     'expected_date': expected_date,
            #     'drugs': drugs
            # })
            # insert new data
            atients.update({"exams": patient["exams"] + [exam_data]}, doc_ids=[patient_id])
        else:
            # update
            # Update existing exam (example: by index)
            exam_index = int(request.form.get('exam_index'))
            updated_exams = patient["exams"]
            updated_exams[exam_index] = exam_data
            patients.update({"exams": updated_exams}, doc_ids=[patient_id])
            

        # change save to update
        # patients.update({'last_visit': exam_date}, doc_ids=[patient_id])



        # OLD insert
        # exams.insert({
        #     'patient_id': patient_id,
        #     'drugs': selected_drugs,
        #     'image': image_path
        # })
        return redirect(url_for('manage_patients'))

    return render_template(
        'exam.html',
        patient=patient,
    )
    
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