from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
from collections import defaultdict
from tinydb import Query, TinyDB
from shared_db import patients_table as patients, exams_table as exams
from unicodedata import normalize

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

    # Parse dates if provided
    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    # Calculate number of days in range for Avg Daily Usage
    if start and end:
        num_days = (end - start).days + 1
    else:
        num_days = 30 # fallback

    # --- MATCHING LOGIC START ---
    # Load purchases for history lookup
    try:
        from routes.mua_thuoc import purchases_table
        all_purchases = purchases_table.all()
    except Exception as e:
        print(f"Error accessing purchases table: {e}")
        all_purchases = []

    # Pre-process purchases by drug name
    drug_purchases_map = defaultdict(list)
    
    # Store purchase data in range for logical union
    purchased_in_range_qty = defaultdict(int)

    for p in all_purchases:
        p_date_str = p.get('date_buy')
        p_date = None
        if p_date_str:
             try: 
                 p_date = datetime.strptime(p_date_str, "%Y-%m-%d")
             except: pass

        # Filter for "In Range" purchases to show in list even if not sold
        in_range = False
        if start and end and p_date:
             if start <= p_date <= end:
                 in_range = True

        for d in p.get('drugs', []):
            d_name = d.get('name', '').strip()
            if d_name:
                # Normalize key
                d_key = normalize('NFC', d_name)
                record = {
                    'date': p_date_str,
                    'quantity': d.get('quantity'),
                    'ppu': d.get('ppu'),
                    'buy_price': d.get('buy_price')
                }
                drug_purchases_map[d_key].append(record)
                
                if in_range:
                    try:
                        qty = int(d.get('quantity', 0))
                        purchased_in_range_qty[d_key] += qty
                    except: pass
    
    # Sort each drug's purchase history by date descending
    for d_name in drug_purchases_map:
        history = drug_purchases_map[d_name]
        history.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        
        # Calculate Trend
        for i in range(len(history)):
            current = history[i]
            # default
            current['trend'] = 'same'
            
            if i + 1 < len(history):
                prev = history[i+1]
                try:
                    c_price = float(current.get('ppu') or 0)
                    p_price = float(prev.get('ppu') or 0)
                    
                    if c_price > p_price:
                        current['trend'] = 'up'
                    elif c_price < p_price:
                        current['trend'] = 'down'
                except Exception:
                    pass
    # --- MATCHING LOGIC END ---

    # Aggregate drug quantities from patients -> exams
    totals = defaultdict(int)
    daily_sales = defaultdict(lambda: defaultdict(int)) # drug -> date -> qty
    
    # Iterate over all patients
    for patient in patients.all():
        # Iterate over each exam for the patient
        for exam in patient.get('exams', []):
            try:
                date_str = exam.get('exam_date', '')
                if not date_str:
                    continue
                exam_date = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                continue

            # Date filtering
            if start and exam_date < start:
                continue
            if end and exam_date > end:
                continue

            # Sum up drugs
            for drug in exam.get('drugs', []):
                try:
                    qty = int(float(drug.get('quantity', 0) or 0))
                except ValueError:
                    qty = 0
                    
                if qty > 0:
                    d_name = drug.get('name', 'Unknown')
                    # Normalize key for consistency
                    key = normalize('NFC', d_name.strip())
                    totals[key] += qty
                    daily_sales[key][date_str] += qty

    # Convert to list of dicts for template
    drug_totals = []
    unmatched_drugs = []

    # Union of all drugs involved (sold OR purchased in range)
    all_drug_names = set(totals.keys()) | set(purchased_in_range_qty.keys())

    for name in all_drug_names:
        qty_sold = totals.get(name, 0)
        history = drug_purchases_map.get(name, [])
        
        # Check for Unmatched Warning (Sold but NEVER purchased ever)
        if qty_sold > 0 and not history and name != 'Unknown':
             unmatched_drugs.append(name)
        
        # Safety Stock Calculation
        # Formula: (Max Daily Usage * Max Lead Time) - (Avg Daily Usage * Avg Lead Time)
        # Avg Lead Time = 3, Max Lead Time = 5 (Requested variation)
        
        max_daily_usage = 0
        if daily_sales.get(name):
             max_daily_usage = max(daily_sales[name].values())
        
        avg_daily_usage = qty_sold / num_days if num_days > 0 else 0
        
        safety_stock = (max_daily_usage * 5) - (avg_daily_usage * 3)
        safety_stock = max(0, int(safety_stock)) # Ensure non-negative integer

        drug_totals.append({
            "name": name, 
            "quantity": qty_sold if qty_sold > 0 else 0, # Pass 0 if no sales
            "last_purchases": history[:3],
            "purchased_in_range": purchased_in_range_qty.get(name, 0), # Optional: show bought qty too?
            "safety_stock": safety_stock
        })

    # Sort totals by quantity desc, then by safety stock
    drug_totals.sort(key=lambda x: (x['quantity'], x['safety_stock']), reverse=True)

    return render_template(
        'drug_sold.html',
        drug_totals=drug_totals,
        unmatched_drugs=unmatched_drugs,
        start_date=start_date,
        end_date=end_date
    )

# ==========================================
# OLD CODE (Commented out for backup)
# ==========================================
# from flask import Blueprint, render_template, request
# from datetime import datetime, timedelta
# from collections import defaultdict
# from tinydb import Query, TinyDB
# from app import exams   # import your TinyDB table from app/__init__.py
# 
# reports_bp = Blueprint('reports', __name__)
# 
# @reports_bp.route('/drug_sold')
# def drug_sold():
#     start_date = request.args.get('start_date')
#     end_date = request.args.get('end_date')
# 
#     # Default to current month if not specified
#     if not start_date or not end_date:
#         now = datetime.now()
#         # First day of month
#         start_date = now.replace(day=1).strftime("%Y-%m-%d")
#         
#         # Last day of month
#         if now.month == 12:
#             next_month = now.replace(year=now.year + 1, month=1, day=1)
#         else:
#             next_month = now.replace(month=now.month + 1, day=1)
#         
#         end_date = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
# 
#     start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
#     end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
# 
#     # Load purchases for history lookup
#     db_purchases = TinyDB('db_mua_thuoc.json', encoding='utf-8')
#     purchases_table = db_purchases.table('purchases')
#     all_purchases = purchases_table.all()
# 
#     # Pre-process purchases by drug name
#     drug_purchases_map = defaultdict(list)
#     for p in all_purchases:
#         p_date = p.get('date_buy')
#         for d in p.get('drugs', []):
#             d_name = d.get('name', '').strip()
#             if d_name:
#                 record = {
#                     'date': p_date,
#                     'quantity': d.get('quantity'),
#                     'ppu': d.get('ppu'),
#                     'buy_price': d.get('buy_price')
#                 }
#                 drug_purchases_map[d_name].append(record)
#     
#     # Sort each drug's purchase history by date descending
#     for d_name in drug_purchases_map:
#         drug_purchases_map[d_name].sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
# 
#     totals = defaultdict(int)
#     for exam in exams.all():
#         try:
#             exam_date = datetime.strptime(exam.get('exam_date', ''), "%Y-%m-%d")
#         except Exception:
#             continue
# 
#         if start and exam_date < start:
#             continue
#         if end and exam_date > end:
#             continue
# 
#         for drug in exam.get('drugs', []):
#             qty = int(drug.get('quantity', 0) or 0)
#             totals[drug.get('name', 'Unknown')] += qty
# 
#     drug_totals = []
#     unmatched_drugs = []
#     
#     for name, qty in totals.items():
#         history = drug_purchases_map.get(name, [])
#         if not history:
#              unmatched_drugs.append(name)
#         
#         drug_totals.append({
#             "name": name, 
#             "quantity": qty,
#             "last_purchases": history[:3]
#         })
# 
#     # Sort totals by quantity desc
#     drug_totals.sort(key=lambda x: x['quantity'], reverse=True)
# 
#     return render_template(
#         'drug_sold.html',
#         drug_totals=drug_totals,
#         unmatched_drugs=unmatched_drugs,
#         start_date=start_date,
#         end_date=end_date
#     )