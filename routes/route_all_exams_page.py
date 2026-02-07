from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from tinydb import Query
from collections import defaultdict

#  the database

exams_list_bp = Blueprint('route_all_exams_page', __name__)
from shared_db import db, patients_table as patients

@exams_list_bp.route('/danh_sach_kham_benh', methods = ['GET', 'POST'])
def get_exam_list():
    if request.method == 'GET':
        # get patients table
        all_patients = patients.all()
        
        all_exams = []
        for patient in all_patients:
            for exam in patient.get('exams', []):
                try:
                    service_fee = int(float(exam.get("service_fee") or 0))
                except (ValueError, TypeError):
                    service_fee = 0

                drug_total = 0
                drugs = exam.get("drugs", [])
                if isinstance(drugs, list):
                    for drug in drugs:
                        try:
                            # Use float first to handle cases like "1000.0"
                            price = int(float(drug.get("price") or 0))
                            quantity = int(float(drug.get("quantity") or 0))
                            drug_total += price * quantity
                        except (ValueError, TypeError, AttributeError):
                            continue
                    
                kid_name = exam.get("kid_name") or patient.get("kid_name", "")
                parent_name = exam.get("parent_name") or patient.get("name", "")
                exam_with_patient = {
                        "kid_name": kid_name,
                        "parent_name": parent_name,
                        "phone": patient.get("phone", ""),
                        "exam_date": exam.get("exam_date", ""),
                        "exam_id": exam.get("id", ""),
                        "paid_status": exam.get("paid_status", False),
                        "patient_id": patient.get("id"), # UUID
                        "history": exam.get("history", ""),
                        "drugs": exam.get("drugs", []),
                        "service_fee": exam.get("service_fee", "0"),
                        "service_fee": exam.get("service_fee", "0"),
                        "total_money": service_fee + drug_total,
                        "address": patient.get("address", "unknown address"),
                        "department": exam.get("department", "PK Nhi"),
                        "created_by_name": exam.get("created_by_name", "")                        
                }
                    
                all_exams.append(exam_with_patient)
        # all_exams = sorted(all_exams, key=lambda x: x.get('exam_date', ''), reverse=True)

        # group all_exams to year-month, split paid/unpaid
        # 1. convert exam_date to datetime
        for exam in all_exams:
            try:
                exam["exam_dt"] = datetime.strptime(exam["exam_date"], "%Y-%m-%d")
            except Exception:
                exam["exam_dt"] = datetime.min
        # 2. group by year-month
        grouped = defaultdict(lambda: {"paid": [], "unpaid": [], "subtotal_paid": 0, "subtotal_unpaid": 0})

        for exam in all_exams:
            ym = exam["exam_dt"].strftime("%Y-%m")
            if exam["paid_status"]:
                grouped[ym]["paid"].append(exam)
                grouped[ym]["subtotal_paid"] += exam["total_money"]
            else:
                grouped[ym]["unpaid"].append(exam)
                grouped[ym]["subtotal_unpaid"] += exam["total_money"]
        # 3. sort months Z - A
        # After grouping
        for ym, data in grouped.items():
            data["paid"] = sorted(data["paid"], key=lambda x: x["exam_dt"], reverse=True)
            data["unpaid"] = sorted(data["unpaid"], key=lambda x: x["exam_dt"], reverse=True)
        sorted_months = sorted(grouped.keys(), reverse=True)
        # 4. Keep 3, the rest is paged
        current_months = sorted_months[:3]
        older_months = sorted_months[3:]
        # paging
        PAGE_SIZE = 1
        page = int(request.args.get("page", 1))
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE

        older_months_page = older_months[start:end]
        total_pages = (len(older_months) + PAGE_SIZE - 1) // PAGE_SIZE
        has_next = page < total_pages

        return render_template('all_exams_page.html', grouped=grouped, exams = all_exams, current_months = current_months, older_months=older_months_page, page=page, total_pages=total_pages,has_next=has_next)

# mark paid status - toggle button
@exams_list_bp.route('/api/mark_paid', methods=['POST'])
def mark_paid():
    try:
        data = request.get_json()
        patient_id = data.get('patient_id') # UUID String
        # print(patient_id)
        exam_id = data.get('exam_id')
        # print(exam_id)
        patients = db.table('patients')
        
        # Find patient by UUID
        # results = patients.search(Query().id == patient_id) # Using shared_db instance
        # Actually in this file we imported 'patients' as 'patients_table' alias 'patients'
        # But look at line 9: `from shared_db import db, patients_table as patients`
        
        results = patients.search(Query().id == patient_id)

        if not results:
            return jsonify({"success": False, "error": "Patient_id not foud"}), 404
        
        patient = results[0]

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
            patients.update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
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
