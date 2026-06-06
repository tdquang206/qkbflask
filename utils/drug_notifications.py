from unicodedata import normalize

from rapidfuzz import fuzz

from shared_db import drugs_table


def _normalize_name(name):
    if not name:
        return ""
    return normalize('NFC', str(name).strip().lower())


def _parse_price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_matching_drug(purchase_name):
    purchase_name_norm = _normalize_name(purchase_name)
    if not purchase_name_norm:
        return None

    all_drugs = drugs_table.all()
    best_match = None
    best_score = 0

    for drug in all_drugs:
        drug_name = drug.get('name', '')
        if not drug_name:
            continue

        drug_name_norm = _normalize_name(drug_name)
        if drug_name_norm == purchase_name_norm:
            return drug

        score = fuzz.partial_ratio(purchase_name_norm, drug_name_norm)
        if score > best_score:
            best_score = score
            best_match = drug

    return best_match if best_score >= 80 else None


def build_price_notifications(purchase_drugs):
    notifications = []
    if not isinstance(purchase_drugs, list):
        return notifications

    for item in purchase_drugs:
        if not isinstance(item, dict):
            continue

        name = item.get('name', '')
        buy_price = _parse_price(item.get('buy_price'))
        if not name or buy_price is None or buy_price <= 0:
            continue

        matched = _find_matching_drug(name)
        if not matched:
            continue

        sell_price = _parse_price(matched.get('sell_price'))
        if sell_price is None or sell_price <= 0:
            continue

        if buy_price > 0.8 * sell_price:
            notifications.append({
                'drug_id': matched.doc_id,
                'drug_name': matched.get('name'),
                'buy_price': buy_price,
                'sell_price': sell_price,
                'message': f'Check sell price for {matched.get("name") or name}',
                'edit_path': f'/edit_drug/{matched.doc_id}'
            })

    return notifications
