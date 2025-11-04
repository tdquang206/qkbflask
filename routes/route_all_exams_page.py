from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from tinydb import TinyDB, Query

#  the database

exams_list_bp = Blueprint('route_all_exams_page', __name__)
db = TinyDB('db.json')

@exams_list_bp.route('/danh_sach_kham_benh', methods = ['GET', 'POST'])
def get_exam_list():
    if request.method == 'GET':
        # get patients table
        patients = db.table('patients')
        all_patients = patients.all()
        print(f"Found {len(all_patients)} patients")  # DEBUG
        
        all_exams = []
        for patient in all_patients:
            for exam in patient.get('exams', []):
                try:
                    service_fee = int(exam.get("service_fee", "0") or 0)
                except (ValueError, TypeError):
                    service_fee = 0

                drug_total = 0
                drugs = exam.get("drugs", [])
                if isinstance(drugs, list):
                    for drug in drugs:
                        try:
                            price = int(drug.get("price", "0") or 0)
                            quantity = int(drug.get("quantity", "0") or 0)
                            drug_total += price * quantity
                        except (ValueError, TypeError, AttributeError):
                            continue
            exam_with_patient = {
                    "kid_name": patient.get("kid_name", ""),
                    "parent_name": patient.get("name", ""),
                    "phone": patient.get("phone", ""),
                    "exam_date": exam.get("exam_date", ""),
                    "exam_id": exam.get("id", ""),
                    "patient_id": patient.doc_id,
                    "history": exam.get("history", ""),
                    "drugs": exam.get("drugs", []),
                    "service_fee": exam.get("service_fee", "0"),
                    "total_money": service_fee + drug_total                       
            }
                
            all_exams.append(exam_with_patient)
        print(f"Total exams found: {len(all_exams)}")  # DEBUG
        all_exams = sorted(all_exams, key=lambda x: x.get('exam_date', ''), reverse=True)
        return render_template('all_exams_page.html', exams = all_exams)




