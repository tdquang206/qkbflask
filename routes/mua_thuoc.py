from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from tinydb import TinyDB, Query
import uuid

mua_thuoc_bp = Blueprint('mua_thuoc', __name__)
db = TinyDB('db_mua_thuoc.json', encoding='utf-8')
purchases_table = db.table('purchases')

Drug = Query()

# Add new
@mua_thuoc_bp.route('/mua_thuoc', methods=['GET','POST'])
def mua_thuoc():
    if request.method == 'POST':
        data = request.get_json()  # parse JSON body

        date_buy = data.get('date_buy')
        paid = bool(data.get('paid'))
        note = data.get('note')

        drugs = []
        for d in data.get('drugs', []):
            if d.get('name', '').strip():
                drugs.append({
                    'name': d.get('name'),
                    'quantity': int(d.get('quantity', 0)),
                    'buy_price': float(d.get('buy_price', 0)),
                    'note': d.get('note', '')
                })

        purchase_data = {
            'uuid': str(uuid.uuid4()),
            'date_buy': date_buy,
            'paid': paid,
            'note': note,
            'drugs': drugs,
            'submit_time': datetime.now().strftime('%y%m%d%H%M%S')
        }

        purchases_table.insert(purchase_data)
        return jsonify({'status': 'success', 'data': purchase_data})

    # GET request → show history
    purchases = purchases_table.all()

    # sort by date (latest first)
    purchases = sorted(purchases, key=lambda x: x.get('date_buy', ''), reverse=True)

    # group unpaid first
    unpaid = [p for p in purchases if not p.get('paid')]
    paid = [p for p in purchases if p.get('paid')]
    grouped = unpaid + paid

    return render_template('mua_thuoc.html', purchases=grouped)


# Delete
@mua_thuoc_bp.route('/mua_thuoc/delete/<purchase_uuid>', methods=['DELETE'])
def mua_thuoc_delete(purchase_uuid):
    Purchase = Query()
    deleted = purchases_table.remove(Purchase.uuid == purchase_uuid)
    if deleted:
        return jsonify({"status": "deleted", "uuid": purchase_uuid})
    return jsonify({"status": "not found"}), 404


# Update, Edit
@mua_thuoc_bp.route('/mua_thuoc/edit/<purchase_uuid>', methods=['PUT'])
def mua_thuoc_edit(purchase_uuid):
    data = request.get_json()

    date_buy = data.get('date_buy')
    paid = bool(data.get('paid'))
    note = data.get('note')

    drugs = []
    for d in data.get('drugs', []):
        if d.get('name', '').strip():
            drugs.append({
                'name': d.get('name'),
                'quantity': int(d.get('quantity', 0)),
                'buy_price': float(d.get('buy_price', 0)),
                'note': d.get('note', '')
            })

    updated_data = {
        'date_buy': date_buy,
        'paid': paid,
        'note': note,
        'drugs': drugs,
        'submit_time': datetime.now().strftime('%y%m%d%H%M%S')
    }
    
    Purchase = Query()
    updated = purchases_table.update(updated_data, Purchase.uuid == purchase_uuid)
    if updated: 
        return jsonify({'status': 'success', 'uuid': purchase_uuid, 'data': updated_data})
    return jsonify({'status': 'not found'}), 404

    
    
    