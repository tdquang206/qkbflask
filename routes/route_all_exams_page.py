from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from tinydb import Query
from collections import defaultdict
from flask_login import login_required, current_user

#  the database

exams_list_bp = Blueprint('route_all_exams_page', __name__)
from shared_db import db, patients_table as patients, money_log_table

@exams_list_bp.route('/danh_sach_kham_benh', methods = ['GET', 'POST'])
def get_exam_list():
    if request.method == 'GET':
        # get patients table
        all_patients = patients.all()
        
        # load existing money-received records so we can display them in the
        # list.  We only care about the most recent entry for each exam; if
        # there are multiple records we'll keep the last one (same logic as a
        # tinydb search sorted by timestamp would produce).
        raw_logs = money_log_table.all()
        money_map = {}
        for log in raw_logs:
            exam_id = log.get('exam_id')
            if not exam_id:
                continue
            # keep the latest by timestamp string (ISO format sorts lexicographically)
            if exam_id not in money_map or log.get('timestamp', '') > money_map[exam_id].get('timestamp', ''):
                money_map[exam_id] = log

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
                        "total_money": service_fee + drug_total,
                        "address": patient.get("address", "unknown address"),
                        "department": exam.get("department", "PK Nhi"),
                        "created_by_name": exam.get("created_by_name", "")                        
                }
                    
                all_exams.append(exam_with_patient)

        # Parse dates to datetime objects for accurate sorting and grouping
        for exam in all_exams:
            try:
                exam["exam_dt"] = datetime.strptime(exam["exam_date"], "%Y-%m-%d")
            except Exception:
                exam["exam_dt"] = datetime.min

        # Filter all unpaid exams for the top-level scrollable panel
        # Sort unpaid exams descending by date (newest first) by default
        unpaid_exams = [e for e in all_exams if not e.get("paid_status", False)]
        unpaid_exams = sorted(unpaid_exams, key=lambda x: x.get("exam_date", ""), reverse=True)

        # Group all exams by year-month for the interactive month view
        grouped = defaultdict(lambda: {"paid": [], "unpaid": [], "subtotal_paid": 0, "subtotal_unpaid": 0})
        for exam in all_exams:
            ym = exam["exam_dt"].strftime("%Y-%m")
            if exam["paid_status"]:
                grouped[ym]["paid"].append(exam)
                grouped[ym]["subtotal_paid"] += exam["total_money"]
            else:
                grouped[ym]["unpaid"].append(exam)
                grouped[ym]["subtotal_unpaid"] += exam["total_money"]

        # Sort entries inside each month by exam date (newest first)
        for ym, data in grouped.items():
            data["paid"] = sorted(data["paid"], key=lambda x: x["exam_dt"], reverse=True)
            data["unpaid"] = sorted(data["unpaid"], key=lambda x: x["exam_dt"], reverse=True)

        # Get list of all available months sorted descending (newest first)
        sorted_months = sorted(grouped.keys(), reverse=True)
        # Default active months are the last 3 months (or fewer if less than 3 exist)
        default_selected_months = sorted_months[:3]

        return render_template('all_exams_page.html', 
                               grouped=grouped,
                               sorted_months=sorted_months,
                               default_selected_months=default_selected_months,
                               unpaid_exams=unpaid_exams,
                               money_map=money_map)

# mark paid status - toggle button
@exams_list_bp.route('/api/mark_paid', methods=['POST'])
@login_required
def mark_paid():
    """Toggle the paid status for an exam and optionally log the real amount.

    Request payload may include ``real_amount`` (number).  When the status is
    flipped to ``True`` we record a ledger entry containing the amount, the
    user who performed the action and a timestamp.  This lets the accounting
    team generate in‑out reports without modifying the original patient
    records.
    """
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')  # UUID String
        exam_id = data.get('exam_id')
        real_amount = data.get('real_amount')
        patients = db.table('patients')

        results = patients.search(Query().id == patient_id)

        if not results:
            return jsonify({"success": False, "error": "Patient_id not found"}), 404

        patient = results[0]

        updated = False
        new_status = None
        for exam in patient.get('exams', []):
            if exam.get('id') == exam_id:
                current_status = exam.get('paid_status', False)
                exam['paid_status'] = not current_status
                new_status = exam['paid_status']
                updated = True
                break

        if updated:
            patients.update({'exams': patient['exams']}, doc_ids=[patient.doc_id])

            # if we just marked it paid and there is a real_amount provided,
            # append a ledger record
            if new_status and real_amount is not None:
                try:
                    amount_int = int(float(real_amount))
                except (ValueError, TypeError):
                    amount_int = 0

                ledger_entry = {
                    'patient_id': patient_id,
                    'exam_id': exam_id,
                    'amount': amount_int,
                    'timestamp': datetime.utcnow().isoformat(),
                    'user': current_user.username if hasattr(current_user, 'username') else None
                }
                money_log_table.insert(ledger_entry)

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
