from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from tinydb import TinyDB, Query
import uuid

mua_thuoc_bp = Blueprint('mua_thuoc', __name__)
mua_thuoc_bp = Blueprint('mua_thuoc', __name__)
from utils.storage import EncryptedJSONStorage
db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage)
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
        total_cost = data.get('totalCost')

        drugs = []
        for d in data.get('drugs', []):
            if d.get('name', '').strip():
                drugs.append({
                    'name': d.get('name'),
                    'quantity': int(d.get('quantity', 0)),
                    'buy_price': float(d.get('buy_price', 0)),
                    'note': d.get('note', ''),
                    'ppu': d.get('ppu',''),
                })

        purchase_data = {
            'uuid': str(uuid.uuid4()),
            'date_buy': date_buy,
            'paid': paid,
            'note': note,
            'drugs': drugs,
            'total_cost': total_cost,
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
@mua_thuoc_bp.route('/mua_thuoc/delete/<purchase_uuid>', methods=['DELETE', 'POST'])
def mua_thuoc_delete(purchase_uuid):
    Purchase = Query()
    deleted = purchases_table.remove(Purchase.uuid == purchase_uuid)
    if deleted:
        # return JSON for API DELETE or redirect for form POST
        if request.method == 'DELETE' or request.is_json:
            return jsonify({"status": "deleted", "uuid": purchase_uuid})
        return redirect(url_for('mua_thuoc.mua_thuoc'))
    if request.method == 'DELETE' or request.is_json:
        return jsonify({"status": "not found"}), 404
    return redirect(url_for('mua_thuoc.mua_thuoc'))


# Update, Edit
@mua_thuoc_bp.route('/mua_thuoc/edit/<purchase_uuid>', methods=['GET', 'POST'])
def mua_thuoc_edit(purchase_uuid):
    Purchase = Query()
    purchase = purchases_table.get(Purchase.uuid == purchase_uuid)
    if not purchase:
        return "Purchase not found", 404

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            date_buy = data.get('date_buy')
            paid = bool(data.get('paid'))
            note = data.get('note')
            total_cost = data.get('totalCost')
            drugs_in = data.get('drugs', [])
            drugs = []
            for d in drugs_in:
                if d.get('name','').strip():
                    drugs.append({
                        'name': d.get('name'),
                        'quantity': int(d.get('quantity',0)),
                        'buy_price': float(d.get('buy_price',0)),
                        'note': d.get('note',''),
                        'ppu': d.get('ppu',''),
                    })
        else: 
        # form submission
            date_buy = request.form.get('date_buy')
            paid = bool(request.form.get('paid'))
            note = request.form.get('note')
            total_cost = request.form.get('totalCost')

            drugs = []
            # assuming you send drugs[] as multiple form fields
            names = request.form.getlist('drug_name')
            quantities = request.form.getlist('drug_quantity')
            prices = request.form.getlist('drug_buy_price')
            notes = request.form.getlist('drug_note')
            ppu = request.form.getlist('ppu')

            for i in range(len(names)):
                if names[i].strip():
                    drugs.append({
                        'name': names[i],
                        'quantity': int(quantities[i] or 0),
                        'buy_price': float(prices[i] or 0),
                        'note': notes[i]
                    })

        updated_data = {
            'date_buy': date_buy,
            'paid': paid,
            'note': note,
            'drugs': drugs,
            'total_cost': total_cost,
            'submit_time': datetime.now().strftime('%y%m%d%H%M%S')
        }

        purchases_table.update(updated_data, Purchase.uuid == purchase_uuid)
        return jsonify({"status": "success", "uuid": purchase_uuid})
        # return redirect(url_for('mua_thuoc.mua_thuoc'))

    # GET: render the edit page with current purchase data
    return render_template('edit_mua_thuoc.html', purchase=purchase)

    
    
    