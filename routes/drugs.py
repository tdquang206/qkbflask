from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from tinydb import Query, TinyDB
from rapidfuzz import fuzz
from shared_db import drugs_table as drugs
import math
import json
import os
import html as _html
import requests as _requests
from datetime import datetime
from unicodedata import normalize
from collections import defaultdict

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


def _fmt_price(value):
    """Round up to nearest 500, then format with k/m suffix."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return '-'
    if value <= 0:
        return '-'
    rounded = math.ceil(value / 500) * 500
    if rounded >= 1_000_000:
        m = rounded / 1_000_000
        return f'{int(m)}m' if m == int(m) else f'{m:.1f}m'
    if rounded >= 1_000:
        k = rounded / 1_000
        if k >= 1_000:
            return f'{int(k):,}k' if k == int(k) else f'{k:,.1f}k'
        return f'{int(k)}k' if k == int(k) else f'{k:.1f}k'
    return str(int(rounded))


def _generate_drugs_html(drug_rows, timestamp):
    """Build a fully self-contained HTML file for offline viewing."""
    ts = _html.escape(timestamp)
    count = len(drug_rows)

    tbody = ''
    for i, row in enumerate(drug_rows, 1):
        name = _html.escape(row['name'])
        cost = _html.escape(row['cost_fmt'])
        sell = _html.escape(row['sell_fmt'])
        tbody += (
            f'<tr>'
            f'<td class="num">{i}</td>'
            f'<td class="name">{name}</td>'
            f'<td class="cost">{cost}</td>'
            f'<td class="sell">{sell}</td>'
            f'</tr>\n'
        )

    return f'''<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thuoc - {ts}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#1a1a1a;color:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:1.25rem}}
h1{{color:#00d1b2;font-size:1.4rem;margin-bottom:.2rem}}
.meta{{color:#888;font-size:.82rem;margin-bottom:1rem}}
.search-wrap{{margin-bottom:1rem}}
#search{{background:rgba(255,255,255,.07);border:1px solid #333;border-radius:8px;
  color:#f5f5f5;font-size:1rem;padding:.55rem 1rem;width:100%;max-width:420px;outline:none}}
#search:focus{{border-color:#00d1b2;box-shadow:0 0 0 2px rgba(0,209,178,.2)}}
table{{width:100%;border-collapse:collapse;background:#242424;border-radius:10px;
  overflow:hidden;box-shadow:0 4px 15px rgba(0,0,0,.35)}}
thead th{{background:#1e1e1e;color:#999;font-size:.72rem;letter-spacing:1px;
  text-transform:uppercase;padding:.7rem 1rem;text-align:left;border-bottom:2px solid #333}}
tbody td{{padding:.65rem 1rem;border-bottom:1px solid #2b2b2b;vertical-align:middle}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover{{background:rgba(255,255,255,.03)}}
.num{{color:#555;width:2.8rem;text-align:right;font-size:.82rem}}
.name{{font-weight:500}}
.cost{{color:#888;font-family:"Consolas","Monaco",monospace;font-weight:600;
  text-align:right;min-width:5rem}}
.sell{{color:#00d1b2;font-family:"Consolas","Monaco",monospace;font-weight:700;
  text-align:right;min-width:5rem}}
#no-results{{display:none;text-align:center;color:#555;padding:2.5rem;font-style:italic}}
.footer{{color:#444;font-size:.75rem;text-align:center;margin-top:1.5rem}}
</style>
</head>
<body>
<h1>Danh s&#225;ch thu&#7889;c</h1>
<div class="meta">
  C&#7853;p nh&#7853;t: <strong>{ts}</strong>
  &nbsp;&middot;&nbsp; <span id="count">{count}</span> thu&#7889;c
</div>
<div class="search-wrap">
    <input id="search" type="text" placeholder="T&#236;m thu&#7889;c..." oninput="doFilter(this.value)" autocomplete="off">
</div>
<table id="tbl">
  <thead>
    <tr>
      <th class="num">#</th>
      <th>T&#234;n thu&#7889;c</th>
      <th style="text-align:right">Gi&#225; nh&#7853;p</th>
      <th style="text-align:right">Gi&#225; b&#225;n</th>
    </tr>
  </thead>
  <tbody id="tbody">
{tbody}  </tbody>
</table>
<div id="no-results">Kh&#244;ng t&#236;m th&#7845;y thu&#7889;c ph&#249; h&#7907;p.</div>
<div class="footer">QKB Offline Export &middot; {ts}</div>
<script>
(function(){{
  var rows = Array.from(document.querySelectorAll("#tbody tr"));
  var noRes = document.getElementById("no-results");
  var countEl = document.getElementById("count");
  function norm(s) {{ return s.toLowerCase().normalize("NFC"); }}
  window.doFilter = function(q) {{
    q = norm(q.trim());
    var shown = 0;
    rows.forEach(function(r) {{
      var visible = !q || norm(r.cells[1].textContent).includes(q);
      r.style.display = visible ? "" : "none";
      if (visible) shown++;
    }});
    countEl.textContent = shown;
    noRes.style.display = (shown === 0 && q) ? "block" : "none";
  }};
}})();
</script>
</body>
</html>'''


@drugs_bp.route('/api/drugs/send_discord', methods=['POST'])
def api_send_drugs_discord():
    SETTINGS_FILE = 'user_settings.json'
    if not os.path.exists(SETTINGS_FILE):
        return jsonify({'error': 'Settings file not found'}), 400
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    webhook_url = settings.get('discord_webhook_url', '').strip()
    if not webhook_url:
        return jsonify({'error': 'Discord webhook URL is not configured'}), 400

    # Load all drugs and sort alphabetically
    all_drugs = sorted(drugs.all(), key=lambda d: d.get('name', '').strip().lower())

    # Build latest-cost map from purchase history
    from utils.storage import EncryptedJSONStorage
    purchases_db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage)
    all_purchases = sorted(
        purchases_db.table('purchases').all(),
        key=lambda p: p.get('date_buy', ''),
        reverse=True
    )
    latest_cost_map = {}
    for p in all_purchases:
        for d in p.get('drugs', []):
            key = normalize('NFC', d.get('name', '').strip().lower())
            if key and key not in latest_cost_map:
                ppu = d.get('ppu')
                if ppu:
                    latest_cost_map[key] = float(ppu)

    # Build rows with full name (no truncation for HTML)
    drug_rows = []
    for drug in all_drugs:
        name = drug.get('name', '').strip()
        if not name:
            continue
        key = normalize('NFC', name.lower())
        latest_cost = latest_cost_map.get(key) or drug.get('buy_price') or 0
        sell = drug.get('sell_price') or 0
        drug_rows.append({
            'name': name,
            'cost_fmt': _fmt_price(latest_cost),
            'sell_fmt': _fmt_price(sell),
        })

    if not drug_rows:
        return jsonify({'error': 'No drugs found'}), 400

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html_content = _generate_drugs_html(drug_rows, timestamp)
    file_bytes = html_content.encode('utf-8')
    fname = f"drugs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    try:
        resp = _requests.post(
            webhook_url,
            data={'content': f'Danh sach thuoc - {timestamp}'},
            files={'file': (fname, file_bytes, 'text/html')},
            timeout=15,
        )
        if not resp.ok:
            return jsonify({'error': f'Discord error {resp.status_code}: {resp.text}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'success': True, 'rows': len(drug_rows)})
