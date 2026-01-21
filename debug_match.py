
import json
from collections import defaultdict
from datetime import datetime

# Mock match logic
def test_match():
    # Load Purchases
    try:
        with open('db_mua_thuoc.json', 'r', encoding='utf-8') as f:
            mua_data = json.load(f)
            # TinyDB stores as {"purchases": {"id": doc, ...}}
            # So table.all() returns list of docs
            purchases_dict = mua_data.get('purchases', {})
            all_purchases = list(purchases_dict.values())
    except Exception as e:
        print(f"Error loading purchases: {e}")
        return

    # Load Exams (Sales)
    try:
        with open('db.json', 'r', encoding='utf-8') as f:
            db_data = json.load(f)
            # Find exams. Looks like they are in 'patients' -> 'exams' AND root 'exams'?
            # The app likely uses root 'exams' if using app.exams.all() which implies a separate table?
            # Or maybe it's using the 'exams' Key in _default table?
            # Let's assume root 'exams' key in db.json acts as table for TinyDB('db.json').table('exams')?
            # Or TinyDB('db.json') defaults to _default?
            # Typically app.exams = TinyDB('db.json').table('exams')
            exams_dict = db_data.get('exams', {})
            all_exams = list(exams_dict.values())
    except Exception as e:
        print(f"Error loading exams: {e}")
        return

    print(f"Loaded {len(all_purchases)} purchases and {len(all_exams)} exams")

    # 1. Build Purchase Map
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

    print(f"Purchase Map Keys (sample): {list(drug_purchases_map.keys())[:5]}")
    
    target_drug = "Cellcept 500mg - Hộp 50"
    if target_drug in drug_purchases_map:
        print(f"Found '{target_drug}' in purchases. Count: {len(drug_purchases_map[target_drug])}")
    else:
        print(f"Did NOT find '{target_drug}' in purchases.")
        # Print close matches?
        for k in drug_purchases_map:
            if "Cellcept" in k:
                print(f" - Found similar: '{k}'")

    # 2. Build Sales Map
    totals = defaultdict(int)
    for exam in all_exams:
        for drug in exam.get('drugs', []):
            d_name = drug.get('name', 'Unknown') # Code used to match this without strip?
            # User reported code: totals[drug.get('name', 'Unknown')] += qty
            # Let's see what happens if we use it directly
            qty = int(drug.get('quantity', 0) or 0)
            totals[d_name] += qty

    if target_drug in totals:
        print(f"Found '{target_drug}' in sales. Qty: {totals[target_drug]}")
    else:
        print(f"Did NOT find '{target_drug}' in sales.")
        for k in totals:
            if "Cellcept" in k:
                print(f" - Found similar in sales: '{k}'")

    # 3. Match
    history = drug_purchases_map.get(target_drug, [])
    print(f"Match length: {len(history)}")

test_match()
