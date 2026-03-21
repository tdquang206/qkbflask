"""
Omni-search helpers.

All heavy lifting (scoring, normalisation, per-table search) lives here so
routes/core.py only needs a thin endpoint.

Scoring strategy
----------------
Score tiers (higher = better match):
  240+  exact match
  235+  digit-only exact (phone numbers)
  190+  substring match
  185+  digit substring
  74–189 fuzzy partial / token-set match (rapidfuzz)
  0     below threshold → excluded
"""

import re
import unicodedata
from collections import defaultdict

from flask import url_for
from rapidfuzz import fuzz
from tinydb import TinyDB

from shared_db import patients_table as patients, drugs_table as drugs
from utils.storage import EncryptedJSONStorage


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_purchases_table():
    """Return the purchases TinyDB table (encrypted)."""
    db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage)
    return db.table('purchases')


def normalize_text(value):
    """Lowercase, strip diacritics (Vietnamese), and collapse whitespace."""
    text = str(value or '').strip().lower()
    if not text:
        return ''
    # NFKD decomposes accented chars so combining marks can be stripped
    decomposed = unicodedata.normalize('NFKD', text)
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ' '.join(stripped.split())


def _digits_only(value):
    """Keep only digit characters — improves phone-number matching."""
    return re.sub(r'\D+', '', str(value or ''))


def _score(query, candidate, weight=0, threshold=74):
    """
    Return a relevance score for (query, candidate).

    Returns 0 when below threshold so callers can skip with 'if not score'.
    The 'weight' parameter biases important fields (name > address etc.).
    """
    nq = normalize_text(query)
    nc = normalize_text(candidate)
    if not nq or not nc:
        return 0

    if nq == nc:
        return 240 + weight

    # phone-style digit comparison
    dq, dc = _digits_only(query), _digits_only(candidate)
    if dq and dq == dc:
        return 235 + weight

    if nq in nc:
        # bonus proportional to query length so specificity is rewarded
        return 190 + weight + min(24, len(nq) * 2)

    if dq and dq in dc:
        return 185 + weight

    fuzzy = max(
        fuzz.partial_ratio(nq, nc),
        fuzz.token_set_ratio(nq, nc),
    )
    if fuzzy < threshold:
        return 0
    return int(fuzzy) + weight


def _compact(value, limit=140):
    """Trim a string to at most *limit* characters for card snippets."""
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else f"{text[:limit - 1].rstrip()}..."


def _money(value):
    """Format a numeric value as a Vietnamese currency string."""
    try:
        return f"{float(value):,.0f} đ"
    except (TypeError, ValueError):
        return 'Chưa có giá'


def _latest_exam(patient):
    """Return the most recently-dated exam for a patient, or None."""
    exam_list = patient.get('exams') or []
    if not exam_list:
        return None
    return sorted(
        exam_list,
        key=lambda e: (e.get('exam_date', ''), e.get('submit_time', '')),
        reverse=True,
    )[0]


def _top(matches, limit=5):
    """Sort by score descending, strip the score key, return top N."""
    sorted_matches = sorted(
        matches,
        key=lambda m: (m['score'], m['title'].lower()),
        reverse=True,
    )[:limit]
    for m in sorted_matches:
        m.pop('score', None)
    return sorted_matches


# ---------------------------------------------------------------------------
# Purchase-history pre-computation
# ---------------------------------------------------------------------------

def build_purchase_history_map(all_purchases):
    """
    Build {normalised_drug_name: [purchase_record, ...]} sorted newest-first.

    Called once per search request so we only read the purchases table once
    and share the result between drug and purchase searches.
    """
    history = defaultdict(list)
    for purchase in all_purchases:
        for item in purchase.get('drugs', []):
            name = item.get('name', '').strip()
            if not name:
                continue
            history[normalize_text(name)].append({
                'date_buy': purchase.get('date_buy', ''),
                'quantity': item.get('quantity'),
                'buy_price': item.get('buy_price'),
            })
    for entries in history.values():
        entries.sort(key=lambda x: x.get('date_buy', ''), reverse=True)
    return history


# ---------------------------------------------------------------------------
# Per-table searchers
# ---------------------------------------------------------------------------

def search_patients(query):
    """Search patients by name, child name, phone, and address."""
    matches = []
    for patient in patients.all():
        latest = _latest_exam(patient)
        score = max(
            _score(query, patient.get('name'), weight=32),
            _score(query, patient.get('kid_name'), weight=28),
            _score(query, patient.get('phone'), weight=30),
            _score(query, patient.get('address'), weight=18),
        )
        if not score:
            continue

        name = patient.get('name', '').strip() or 'Chưa có tên phụ huynh'
        kid = patient.get('kid_name', '').strip()

        meta = [
            f"SDT: {patient.get('phone') or 'Chưa có số'}",
            f"Địa chỉ: {patient.get('address') or 'Chưa có địa chỉ'}",
        ]
        if kid:
            meta.insert(0, f"Bé: {kid}")
        if patient.get('last_visit'):
            meta.append(f"Lần khám gần nhất: {patient['last_visit']}")

        if latest:
            hist = _compact(latest.get('history', ''), limit=110)
            snippet = (
                f"Toa gần nhất {latest.get('exam_date', 'không rõ ngày')}: {hist}"
                if hist else
                f"Toa gần nhất {latest.get('exam_date', 'không rõ ngày')}"
            )
        else:
            snippet = 'Chưa có toa khám gần đây.'

        matches.append({
            'title': name,
            'subtitle': kid or 'Bệnh nhân',
            'meta': meta,
            'snippet': snippet,
            'note': 'Chi tiết đầy đủ vẫn dễ thao tác hơn trên PC.',
            'primary_action': {
                'label': 'Mở hồ sơ',
                'url': url_for('patients.view_exams', patient_id=patient.get('id')),
            },
            'secondary_action': {
                'label': 'Sửa thông tin',
                'url': url_for('patients.edit_patient', patient_id=patient.get('id')),
            },
            'score': score,
        })
    return _top(matches)


def search_exams(query):
    """Search exams by ID, history, patient info, and prescribed drug names."""
    matches = []
    for patient in patients.all():
        pname = patient.get('name', '').strip()
        kid = patient.get('kid_name', '').strip()
        phone = patient.get('phone', '').strip()

        for exam in patient.get('exams', []):
            drug_names = ', '.join(
                d.get('name', '').strip()
                for d in exam.get('drugs', []) if d.get('name')
            )
            score = max(
                _score(query, exam.get('id'), weight=36),
                _score(query, exam.get('history'), weight=28),
                _score(query, exam.get('exam_date'), weight=16),
                _score(query, pname, weight=18),
                _score(query, kid, weight=20),
                _score(query, phone, weight=16),
                _score(query, drug_names, weight=26),
            )
            if not score:
                continue

            matches.append({
                'title': exam.get('exam_date') or 'Không rõ ngày khám',
                'subtitle': kid or pname or 'Toa khám',
                'meta': [
                    f"Mã toa: {exam.get('id', '')}",
                    f"Phụ huynh: {pname or 'Chưa có tên'}",
                    f"SDT: {phone or 'Chưa có số'}",
                ],
                'snippet': _compact(
                    exam.get('history', '') or drug_names or 'Chưa có mô tả'
                ),
                'note': 'Mở trên PC để chỉnh toa và file đính kèm thuận tiện hơn.',
                'primary_action': {
                    'label': 'Xem toa',
                    'url': url_for('exam.edit_exam', exam_id=exam.get('id')),
                },
                'score': score,
            })
    return _top(matches)


def search_drugs(query, purchase_history_map):
    """Search drugs by name and SKU; include latest purchase history."""
    matches = []
    for drug in drugs.all():
        name = drug.get('name', '').strip()
        sku = drug.get('sku', '').strip()
        score = max(
            _score(query, name, weight=34),
            _score(query, sku, weight=24),
        )
        if not score:
            continue

        entries = purchase_history_map.get(normalize_text(name), [])[:3]
        history_lines = [
            f"{e.get('date_buy', 'Không rõ ngày')} • {e.get('quantity', '?')} • {_money(e.get('buy_price'))}"
            for e in entries
        ]

        matches.append({
            'title': name or 'Thuốc chưa có tên',
            'subtitle': sku or 'Chưa có SKU',
            'meta': [
                f"Giá bán: {_money(drug.get('sell_price'))}",
                f"Giá nhập: {_money(drug.get('buy_price'))}",
                f"Tồn kho: {drug.get('inventory', 'Chưa rõ')}",
            ],
            'snippet': (
                '3 lần nhập gần nhất: ' +
                (' | '.join(history_lines) if history_lines else 'Chưa có lịch sử mua thuốc.')
            ),
            'note': 'Bản xem nhanh trên mobile, chi tiết chỉnh sửa ở trang thuốc.',
            'primary_action': {
                'label': 'Mở thuốc',
                'url': url_for('drugs.edit_drug', drug_id=drug.doc_id),
            },
            'score': score,
        })
    return _top(matches)


def search_purchases(query, all_purchases):
    """Search purchase orders by date, note, UUID, and drug names."""
    matches = []
    for purchase in all_purchases:
        drug_names = ', '.join(
            d.get('name', '').strip()
            for d in purchase.get('drugs', []) if d.get('name')
        )
        score = max(
            _score(query, purchase.get('date_buy'), weight=14),
            _score(query, purchase.get('note'), weight=20),
            _score(query, drug_names, weight=32),
            _score(query, purchase.get('uuid'), weight=16),
        )
        if not score:
            continue

        matches.append({
            'title': purchase.get('date_buy') or 'Không rõ ngày mua',
            'subtitle': 'Đã thanh toán' if purchase.get('paid') else 'Chưa thanh toán',
            'meta': [
                f"Tổng tiền: {_money(purchase.get('total_cost'))}",
                f"Số mặt hàng: {len(purchase.get('drugs', []))}",
                f"Mã phiếu: {(purchase.get('uuid') or '')[:8]}",
            ],
            'snippet': _compact(
                drug_names or purchase.get('note') or 'Không có ghi chú'
            ),
            'note': 'Phiếu mua thuốc đầy đủ hiển thị tốt hơn trên PC.',
            'primary_action': {
                'label': 'Mở phiếu',
                'url': url_for('mua_thuoc.mua_thuoc_edit', purchase_uuid=purchase.get('uuid')),
            },
            'score': score,
        })
    return _top(matches)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_omni_search(query):
    """
    Execute omni-search across patients, exams, drugs, and purchases.

    Returns a dict ready to be passed to jsonify().
    Requires an active Flask application/request context (for url_for).
    """
    empty = {
        'query': query,
        'groups': {'patients': [], 'exams': [], 'drugs': [], 'mua_thuoc': []},
        'totals': {'patients': 0, 'exams': 0, 'drugs': 0, 'mua_thuoc': 0},
        'has_results': False,
    }

    # Minimum 3 characters to avoid full-table scans on every keystroke
    if len(normalize_text(query)) < 3:
        return empty

    all_purchases = _get_purchases_table().all()
    history_map = build_purchase_history_map(all_purchases)

    groups = {
        'patients': search_patients(query),
        'exams': search_exams(query),
        'drugs': search_drugs(query, history_map),
        'mua_thuoc': search_purchases(query, all_purchases),
    }
    totals = {k: len(v) for k, v in groups.items()}

    return {
        'query': query,
        'groups': groups,
        'totals': totals,
        'has_results': any(totals.values()),
    }
