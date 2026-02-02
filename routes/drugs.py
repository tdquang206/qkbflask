from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from tinydb import Query, TinyDB
from rapidfuzz import fuzz
from shared_db import drugs_table as drugs

drugs_bp = Blueprint('drugs', __name__)

# drugs: view, edit, delete
Drug = Query()

@drugs_bp.route('/drugs', methods=['GET', 'POST'])
def manage_drugs():
    if request.method == 'POST':
        drugs.insert({
            'sku': request.form['sku'],
            'name': request.form['name'],
            'sell_price': float(request.form.get('sell_price', 0)) if request.form.get('sell_price', '').isdigit() else "",
            'buy_price': float(request.form.get('buy_price', 0)) if request.form.get('buy_price', '').isdigit() else "",
            'quantity': int(request.form.get('quantity', 0)) if request.form.get('quantity', '').isdigit() else "",
            'inventory': int(request.form.get('inventory', 0)) if request.form.get('inventory', '').isdigit() else ""
        })
        return redirect(url_for('drugs.manage_drugs'))
    
    
    # Pre-process purchases for history lookup
    # Normalize and group by drug name
    from unicodedata import normalize
    from collections import defaultdict
    
    # Load purchases - using encrypted storage
    from utils.storage import EncryptedJSONStorage
    purchases_db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage)
    purchases_table = purchases_db.table('purchases')
    all_purchases = purchases_table.all()

    drug_purchases_map = defaultdict(list)

    for p in all_purchases:
        p_date = p.get('date_buy')
        for d in p.get('drugs', []):
            d_name = d.get('name', '').strip()
            if d_name:
                key = normalize('NFC', d_name.lower())
                record = {
                    'date': p_date,
                    'quantity': d.get('quantity'),
                    'ppu': d.get('ppu'),
                    'buy_price': d.get('buy_price')
                }
                drug_purchases_map[key].append(record)
    
    # Sort history by date descending
    for key in drug_purchases_map:
        drug_purchases_map[key].sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)

    all_drugs = drugs.all()
    # Attach history to drugs
    for drug in all_drugs:
        name = drug.get('name', '').strip()
        if name:
            key = normalize('NFC', name.lower())
            # Get top 3
            drug['last_purchases'] = drug_purchases_map.get(key, [])[:3]
        else:
            drug['last_purchases'] = []

    return render_template('drugs.html', drugs=all_drugs)

# NOTE: edit drugs
@drugs_bp.route('/edit_drug/<int:drug_id>', methods=['GET', 'POST'])
def edit_drug(drug_id):
    drug = drugs.get(doc_id=drug_id)

    if request.method == 'GET':
        drug_name = drug.get('name', '').lower()
        # get db_mua_thuoc.json with encrypted storage
        from utils.storage import EncryptedJSONStorage
        purchases_db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage).table('purchases')
        # print(purchases_db.all())

        # find purchase history
        purchase_history = []
        for purchase in purchases_db.all():
            for item in purchase.get('drugs', []):
                item_name = item.get('name', '').lower()

                # fuzzy match
                if fuzz.partial_ratio(drug_name, item_name) > 80:
                    purchase_history.append({
                        "date_buy": purchase.get('date_buy'),
                        "quantity": item.get('quantity'),
                        "buy_price": item.get('buy_price'),
                        "note": item.get('note', "")
                    })
        return render_template('edit_drug.html', drug=drug, purchase_history=purchase_history)

    
    if request.method == 'POST':
        drugs.update({
            'sku': request.form['sku'],
            'name': request.form['name'],
            'sell_price': float(request.form.get('sell_price', 0)) if request.form.get('sell_price', '').isdigit() else "",
            'buy_price': float(request.form.get('buy_price', 0)) if request.form.get('buy_price', '').isdigit() else "",
            'quantity': int(request.form.get('quantity', 0)) if request.form.get('quantity', '').isdigit() else "",
            'inventory': int(request.form.get('inventory', 0)) if request.form.get('inventory', '').isdigit() else ""
        }, doc_ids=[drug_id])
        return redirect(url_for('drugs.manage_drugs'))

@drugs_bp.route('/delete_drug/<int:drug_id>')
def delete_drug(drug_id):
    drugs.remove(doc_ids=[drug_id])
    return redirect(url_for('drugs.manage_drugs'))

# get drugs list by ajax
@drugs_bp.route('/api/drugs')
def api_drugs():
    return jsonify(drugs.all())
