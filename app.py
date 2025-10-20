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

# Mới thêm hôm nay
@app.route("/exam/<int:patient_id>/<exam_id>")
def edit_exam(patient_id, exam_id):
    patient = patients.get(doc_id=patient_id)
    exam = next((e for e in patient["exams"] if e["id"] == exam_id), None)
    return render_template("exam.html", patient=patient, exam=exam)


@app.route('/exam/<int:patient_id>', methods=['GET', 'POST'])
def exam(patient_id):
    Patient = Query()
    patient = patients.get(doc_id=patient_id)

    if request.method == "GET":
        exam_id = request.args.get("exam_id")
        exam = None
        if exam_id:
            # look up by UUID
            exam = next((e for e in patient.get("exams", []) if e.get("id") == exam_id), None)
        return render_template("exam.html", patient=patient, exam=exam)

    
    if request.method == 'POST':
        # save state or not
        state = request.form.get('mode')
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
            # get submit time # YYMMDDHHMMSS
            'submit_time' : datetime.now().strftime('%y%m%d%H%M%S')
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
            # inject uuid v4
            exam_data["id"] = str(uuid.uuid4())
            exams_list = patient.get("exams", [])
            patients.update({"exams": exams_list + [exam_data]}, doc_ids=[patient_id])
            # exams.insert(exam_data) Copilot set this one makes broken data
            # Update last_visit
            patients.update({'last_visit': exam_date}, doc_ids=[patient_id])
            return jsonify({"status": "success", "exam_id": exam_data["id"]}), 200


        elif state == 'update':
            exam_id = request.form.get("exam_id")
            exams = patient.get("exams", [])
            updated = False
            for i, exam in enumerate(exams):
                if exam.get("id") == exam_id:
                    # keep the same UUID
                    exam_data["id"] = exam_id
                    exams[i] = exam_data
                    patients.update({"exams": exams}, doc_ids=[patient_id])
                    updated = True
                    break
            if not updated:
                return jsonify({"status": "error", "message": "Exam ID not found"}), 400

            

            return jsonify({"status": "success", "message": "Dữ liệu đã được lưu thành công"}), 200

    return render_template(
        'exam.html',
        patient=patient,
        exam=exam_data
    )

@app.route("/exam/<int:patient_id>/delete", methods=["POST"])
def delete_exam(patient_id):
    print("Delete called for patient:", patient_id)
    print("Form data:", request.form.to_dict())

    patient = patients.get(doc_id=patient_id)
    exam_id = request.form.get("exam_id")

    if not patient:
        print("No patient found with that ID")
        return "Exam not found", 404

    if not exam_id:
        print("No exam_id in form")
        return "Exam not found", 404

    exams = patient.get("exams", [])
    print("Existing exam IDs:", [e.get("id") for e in exams])

    new_exams = [e for e in exams if e.get("id") != exam_id]

    if len(new_exams) != len(exams):
        patients.update({"exams": new_exams}, doc_ids=[patient_id])
        print("Exam deleted:", exam_id)
    else:
        print("Exam_id not matched:", exam_id)

    return redirect(url_for("view_exams", patient_id=patient_id))
    
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