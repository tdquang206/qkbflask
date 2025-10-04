from flask import Blueprint, render_template, request
from datetime import datetime
from collections import defaultdict
from tinydb import Query
from yourapp import exams   # import your TinyDB table from app/__init__.py

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/drug_sold')
def drug_sold():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

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

    drug_totals = [{"name": name, "quantity": qty} for name, qty in totals.items()]

    return render_template(
        'drug_sold.html',
        drug_totals=drug_totals,
        start_date=start_date,
        end_date=end_date
    )