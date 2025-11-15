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
                        "paid_status": exam.get("paid_status", False),
                        "patient_id": patient.doc_id,
                        "history": exam.get("history", ""),
                        "drugs": exam.get("drugs", []),
                        "service_fee": exam.get("service_fee", "0"),
                        "total_money": service_fee + drug_total                       
                }
                    
                all_exams.append(exam_with_patient)
        all_exams = sorted(all_exams, key=lambda x: x.get('exam_date', ''), reverse=True)

        return render_template('all_exams_page.html', exams = all_exams)

# mark paid status - toggle button
@exams_list_bp.route('/api/mark_paid', methods=['POST'])
def mark_paid():
    try:
        data = request.get_json()
        patient_id = int(data.get('patient_id'))
        # print(patient_id)
        exam_id = data.get('exam_id')
        # print(exam_id)
        patients = db.table('patients')
        patient = patients.get(doc_id=patient_id)
        if not patient:
            return jsonify({"success": False, "error": "Patient_id not foud"}), 404

        updated = False
        new_status = None
        for exam in patient.get('exams', []):
            if exam.get('id') == exam_id:

                curent_status = exam.get('paid_status', False)
                exam['paid_status'] = not curent_status
                new_status = exam['paid_status']
                updated = True
                break

        if updated:
            patients.update({'exams': patient['exams']}, doc_ids=[patient_id])
            return jsonify({
                "success": True,
                "message": "Payment updated",
                "paid_status": new_status
            })
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Exam id not found. Unable to update"
                }, 404
            )
    except Exception as e:
        print("Error in /api/mark_paid", e)
        return jsonify({"success": False, "error": str(e)}), 500
