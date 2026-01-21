from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from collections import defaultdict
from tinydb import Query, TinyDB
from app import exams   # import your TinyDB table from app/__init__.py

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/drug_sold')
def drug_sold():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Default to current month if not specified
    if not start_date or not end_date:
        now = datetime.now()
        # First day of month
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        
        # Last day of month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        
        end_date = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")

    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    # Load purchases for history lookup
    db_purchases = TinyDB('db_mua_thuoc.json', encoding='utf-8')
    purchases_table = db_purchases.table('purchases')
    all_purchases = purchases_table.all()

    # Pre-process purchases by drug name
    drug_purchases_map = defaultdict(list)
    for p in all_purchases:
        p_date = p.get('date_buy')
        for d in p.get('drugs', []):
            d_name = d.get('name', '').strip()
            if d_name:
                record = {
                    'date': p_date,
                    'quantity': d.get('quantity'),
                    'ppu': d.get('ppu'),
                    'buy_price': d.get('buy_price')
                }
                drug_purchases_map[d_name].append(record)
    
    # Sort each drug's purchase history by date descending
    for d_name in drug_purchases_map:
        drug_purchases_map[d_name].sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)

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

    drug_totals = []
    unmatched_drugs = []
    
    for name, qty in totals.items():
        history = drug_purchases_map.get(name, [])
        if not history:
             unmatched_drugs.append(name)
        
        drug_totals.append({
            "name": name, 
            "quantity": qty,
            "last_purchases": history[:3]
        })

    # Sort totals by quantity desc
    drug_totals.sort(key=lambda x: x['quantity'], reverse=True)

    return render_template(
        'drug_sold.html',
        drug_totals=drug_totals,
        unmatched_drugs=unmatched_drugs,
        start_date=start_date,
        end_date=end_date
    )