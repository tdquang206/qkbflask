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

    # old html_content: backup of original drugs export page layout
    # It previously included only search, table, and footer.
    product_catalog_js = ','.join([
        f"{{name: {json.dumps(row['name'])}, price: {float(row['sell_price']) if row.get('sell_price') is not None else 0}}}" for row in drug_rows
    ])

    return f'''<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thuoc - {ts}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#1a1a1a;color:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:1rem;max-width:760px;margin:0 auto}}
h1{{color:#00d1b2;font-size:1.35rem;margin-bottom:.4rem}}
.meta{{color:#888;font-size:.84rem;margin-bottom:.9rem}}
.calc-card{{background:#1f1f1f;border:1px solid #2f2f2f;border-radius:16px;padding:1rem;margin-bottom:1rem;box-shadow:0 10px 30px rgba(0,0,0,.18)}}
.calc-card h2{{margin:0 0 .4rem;font-size:1.1rem;color:#7ef2c4}}
.calc-card p{{color:#ccc;font-size:.92rem;line-height:1.5;margin-bottom:.85rem}}
#subtotalInput{{width:100%;min-height:100px;border:1px solid #333;border-radius:14px;background:rgba(255,255,255,.05);color:#f5f5f5;padding:1rem;font-size:1rem;resize:vertical;outline:none}}
#subtotalInput:focus{{border-color:#00d1b2;box-shadow:0 0 0 2px rgba(0,209,178,.16)}}
.calc-actions{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin:.9rem 0}}
.calc-actions button{{width:100%;padding:.95rem 1rem;border:none;border-radius:14px;background:#00d1b2;color:#08120c;font-weight:700;cursor:pointer;min-height:48px}}
.calc-actions button.secondary{{background:#333;color:#f5f5f5}}
.subtotal-result{{margin-top:.85rem;border:1px solid #2f2f2f;border-radius:14px;padding:1rem;background:rgba(255,255,255,.04);min-height:70px}}
.fallback-panel{{margin-top:1rem;padding-top:1rem;border-top:1px solid #2f2f2f}}
.fallback-panel label{{display:block;color:#ccc;margin-bottom:.35rem;font-size:.88rem}}
#fallbackSearch{{width:100%;border:1px solid #333;border-radius:14px;background:rgba(255,255,255,.05);color:#f5f5f5;padding:.95rem;font-size:1rem;outline:none}}
.fallback-matches{{display:grid;gap:.55rem;margin:.75rem 0}}
.match-button{{border:1px solid #333;border-radius:14px;background:#272727;color:#f5f5f5;padding:.95rem;text-align:left;cursor:pointer;transition:transform .15s ease}}
.match-button:hover{{transform:scale(1.01)}}
.fallback-row{{display:grid;grid-template-columns:1fr 110px;gap:.75rem;align-items:center}}
#fallbackQty{{width:100%;border:1px solid #333;border-radius:14px;background:rgba(255,255,255,.05);color:#f5f5f5;padding:.9rem;outline:none;font-size:1rem}}
#addFallbackItem{{width:100%;padding:.95rem 1rem;border:none;border-radius:14px;background:#444;color:#f5f5f5;cursor:pointer;font-size:1rem}}
.result-grid{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:.5rem;margin-top:.75rem}}
.result-grid .header, .result-grid .cell{{padding:.75rem .9rem;border-radius:12px;background:#141414;}}
.result-grid .header{{color:#7ef2c4;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}}
.result-grid .cell{{color:#eee;font-size:.95rem;}}
.result-grid .total-label{{grid-column:span 3;text-align:right;font-weight:700;color:#fff;}}
.total-value{{font-weight:700;color:#00d1b2;text-align:right;}}
.search-wrap{{margin-bottom:1rem}}
#search{{background:rgba(255,255,255,.07);border:1px solid #333;border-radius:14px;
  color:#f5f5f5;font-size:1rem;padding:.75rem 1rem;width:100%;outline:none}}
#search:focus{{border-color:#00d1b2;box-shadow:0 0 0 2px rgba(0,209,178,.2)}}
table{{width:100%;border-collapse:collapse;background:#242424;border-radius:14px;
  overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,.24)}}
thead th{{background:#1e1e1e;color:#999;font-size:.78rem;letter-spacing:.04em;
  text-transform:uppercase;padding:.8rem 1rem;text-align:left;border-bottom:2px solid #333}}
tbody td{{padding:.85rem 1rem;border-bottom:1px solid #2b2b2b;vertical-align:middle}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover{{background:rgba(255,255,255,.04)}}
.num{{color:#777;width:2.8rem;text-align:right;font-size:.85rem}}
.name{{font-weight:500;}}
.cost{{color:#888;font-family:"Consolas","Monaco",monospace;font-weight:600;
  text-align:right;min-width:5rem}}
.sell{{color:#00d1b2;font-family:"Consolas","Monaco",monospace;font-weight:700;
  text-align:right;min-width:5rem}}
#no-results{{display:none;text-align:center;color:#bbb;padding:2.5rem;font-style:italic}}
.footer{{color:#666;font-size:.78rem;text-align:center;margin-top:1.5rem}}
@media (max-width: 680px) {{
  body{{padding:.85rem}}
  h1{{font-size:1.2rem}}
  .calc-card{{padding:.95rem}}
  .calc-actions{{grid-template-columns:1fr;}}
  .fallback-row{{grid-template-columns:1fr;}}
  .result-grid{{grid-template-columns:1fr;}}
  .result-grid .header, .result-grid .cell{{font-size:.95rem;}}
  .result-grid .total-label, .total-value{{text-align:left;}}
  .search-wrap{{margin-bottom:.85rem}}
  thead th{{font-size:.75rem;padding:.75rem .9rem}}
  tbody td{{padding:.75rem .9rem}}
  #subtotalInput{{min-height:110px}}
  #fallbackQty{{width:100%}}
  #addFallbackItem{{font-size:1rem}}
  .result-row{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:.5rem;align-items:center;}}
  .result-row .cell{{padding:.65rem .8rem;background:#181818;border-radius:12px;}}
  .result-row .name{{grid-column:span 2;}}
  @media (max-width: 680px) {{
    .result-grid{{grid-template-columns:1fr;}}
    .result-row{{grid-template-columns:1fr 1fr;}}
    .result-row .name{{grid-column:1 / -1;}}
    .result-row .price, .result-row .qty, .result-row .line{{text-align:left;}}
    .result-grid .header{{display:none;}}
  }}
}}
</style>
</head>
<body>
<h1>Danh s&#225;ch thu&#7889;c</h1>
<div class="meta">
  C&#7853;p nh&#7853;t: <strong>{ts}</strong>
  &nbsp;&middot;&nbsp; <span id="count">{count}</span> thu&#7889;c
</div>
<div class="calc-card">
  <h2>Quick Subtotal Calculator</h2>
  <p>Enter text like “5 product A, 7 product B, 1 product C”. Vietnamese input is supported.</p>
  <textarea id="subtotalInput" placeholder="5 product A, 7 product B, 1 product C"></textarea>
  <div class="calc-actions">
    <button id="calcSubmit" type="button">Calculate</button>
    <button id="calcVoice" type="button" class="secondary">Voice input</button>
  </div>
  <div id="subtotalResult" class="subtotal-result"></div>
  <div class="fallback-panel">
    <label for="fallbackSearch">Fallback product search</label>
    <input id="fallbackSearch" placeholder="Search product..." autocomplete="off">
    <div id="fallbackMatches" class="fallback-matches"></div>
    <div class="fallback-row">
      <input id="fallbackQty" type="number" min="1" value="1">
      <button id="addFallbackItem" type="button">Add item</button>
    </div>
  </div>
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
/* old html_content
   The previous page layout only included the search input and table.
   The subtotal calculator panel was added above for quick product subtotaling.
*/
(function(){{
  var rows = Array.from(document.querySelectorAll("#tbody tr"));
  var noRes = document.getElementById("no-results");
  var countEl = document.getElementById("count");
  function norm(s) {{ return s.toLowerCase().normalize("NFC").replace(/đ/g, 'd'); }}
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

  var productCatalog = [{product_catalog_js}];

  function matchProduct(query) {{
    var normalized = norm(query);
    if (!normalized) return null;
    var exact = productCatalog.find(function(item) {{ return norm(item.name) === normalized; }});
    if (exact) return exact;
    var contains = productCatalog.find(function(item) {{ return norm(item.name).includes(normalized); }});
    if (contains) return contains;
    var best = null;
    var bestScore = 0;
    productCatalog.forEach(function(item) {{
      var name = norm(item.name);
      var score = normalized.split(' ').reduce(function(sum, token) {{
        return sum + (name.includes(token) ? 1 : 0);
      }}, 0);
      if (score > bestScore) {{ bestScore = score; best = item; }}
    }});
    return bestScore >= 1 ? best : null;
  }}

  function parseInput(text) {{
    var segments = text.split(/[,;\n]+/).map(function(s) {{ return s.trim(); }}).filter(Boolean);
    var items = [];
    var unmatched = [];
    var patterns = [
      /^(\d+)\s*(?:x|×|sp|san pham|sản phẩm|product|viên|hộp|chai|pack|pcs)?\s+(.+)$/i,
      /^(.+?)\s*(?:x|×|:|–|-)\s*(\d+)$/i,
      /^(?:mua|take|add)?\s*(\d+)\s+(.+)$/i
    ];

    segments.forEach(function(segment) {{
      var found = false;
      for (var i = 0; i < patterns.length; i++) {{
        var m = segment.match(patterns[i]);
        if (!m) continue;
        var qty = parseInt(m[1], 10);
        var name = m[2] ? m[2].trim() : m[1].trim();
        if (!qty || qty < 1) continue;
        var product = matchProduct(name);
        if (product) {{
          items.push({{ name: product.name, price: product.price, qty: qty }});
          found = true;
          break;
        }}
      }}
      if (!found) {{
        unmatched.push(segment);
      }}
    }});
    return {{ items: items, unmatched: unmatched }};
  }}

  function renderResults(items, unmatched) {{
    var target = document.getElementById('subtotalResult');
    if (!items.length) {{
      target.innerHTML = '<p style="margin:0;color:#f5f5f5">No matching products found. Use the fallback search below.</p>';
      return;
    }}
    var total = 0;
    var rows = items.map(function(item) {{
      var line = item.price * item.qty;
      total += line;
      return '<div class="result-row">' +
        '<div class="cell name">' + item.name + '</div>' +
        '<div class="cell price">' + item.price.toLocaleString() + '</div>' +
        '<div class="cell qty">' + item.qty + '</div>' +
        '<div class="cell line">' + line.toLocaleString() + '</div>' +
        '</div>';
    }}).join('');
    target.innerHTML =
      '<div class="result-grid">' +
      '<div class="header">Product</div><div class="header">Unit</div><div class="header">Qty</div><div class="header">Subtotal</div>' +
      rows +
      '<div class="total-label">Total</div><div class="total-value">' + total.toLocaleString() + '</div>' +
      '</div>' +
      (unmatched && unmatched.length ? '<p style="margin:.75rem 0 0;color:#f5f5f5">Unmatched: ' + unmatched.join('; ') + '</p>' : '');
  }}

  function initFallback() {{
    var searchInput = document.getElementById('fallbackSearch');
    var matches = document.getElementById('fallbackMatches');
    var qtyInput = document.getElementById('fallbackQty');
    var addButton = document.getElementById('addFallbackItem');

    function renderMatches() {{
      matches.innerHTML = '';
      var query = normalize(searchInput.value);
      if (!query) return;
      productCatalog.filter(function(item) {{ return normalize(item.name).includes(query); }}).slice(0, 10).forEach(function(item) {{
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'match-button';
        button.textContent = item.name + ' – ' + item.price.toLocaleString();
        button.addEventListener('click', function() {{
          renderResults([{{ name: item.name, price: item.price, qty: parseInt(qtyInput.value, 10) || 1 }}]);
        }});
        matches.appendChild(button);
      }});
    }}

    searchInput.addEventListener('input', renderMatches);
    addButton.addEventListener('click', function() {{
      var product = matchProduct(searchInput.value);
      if (!product) {{
        matches.innerHTML = '<p style="margin:0;color:#f5f5f5">Không tìm thấy sản phẩm.</p>';
        return;
      }}
      renderResults([{{ name: product.name, price: product.price, qty: parseInt(qtyInput.value, 10) || 1 }}]);
    }});
  }}

  function initVoice() {{
    var button = document.getElementById('calcVoice');
    var recognition = null;
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {{
      var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SpeechRecognition();
      recognition.lang = 'vi-VN';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.addEventListener('result', function(event) {{
        var transcript = event.results[0][0].transcript;
        document.getElementById('subtotalInput').value = transcript;
        document.getElementById('calcSubmit').click();
      }});
      recognition.addEventListener('error', function() {{
        button.textContent = 'Voice not available';
      }});
    }} else {{
      button.style.display = 'none';
    }}
    button.addEventListener('click', function() {{
      if (recognition) recognition.start();
    }});
  }}

  document.getElementById('calcSubmit').addEventListener('click', function() {{
    var input = document.getElementById('subtotalInput').value || '';
    var result = parseInput(input);
    renderResults(result.items, result.unmatched);
  }});

  initFallback();
  initVoice();
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
    if not webhook_url.startswith((
        'https://discord.com/api/webhooks/',
        'https://discordapp.com/api/webhooks/',
    )):
        return jsonify({'error': 'Invalid Discord webhook URL'}), 400

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
            'sell_price': sell,
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
