"""Numeric validation and recorded stock calculations for drug management."""

import math
from unicodedata import normalize


def drug_name_key(name):
    return normalize('NFC', str(name or '').strip().casefold())


def nonnegative_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def parse_drug_form(form, existing=None):
    """Validate every field before writing; retain omitted legacy fields."""
    existing = existing or {}
    values, errors = {}, []
    for field, label in (('sku', 'SKU'), ('name', 'Name')):
        value = form.get(field, existing.get(field, '')).strip()
        values[field] = value
        if field == 'name' and not value:
            errors.append('Name is required.')

    for field, label in (('sell_price', 'Sell price'), ('buy_price', 'Buy price'),
                         ('quantity', 'Quantity'), ('inventory', 'Inventory')):
        if field not in form:
            values[field] = existing.get(field, '')
            continue
        raw = form[field].strip()
        if not raw:
            if existing.get(field) not in (None, ''):
                errors.append(f'{label} cannot be cleared. Enter a number (0 is allowed).')
            values[field] = ''
            continue
        number = nonnegative_number(raw)
        if number is None or (field in ('quantity', 'inventory') and not number.is_integer()):
            kind = 'whole number' if field in ('quantity', 'inventory') else 'number'
            errors.append(f'{label} must be a finite, non-negative {kind}.')
            continue
        values[field] = int(number) if field in ('quantity', 'inventory') else number
    return values, errors


def drug_stock_details(name, purchases, patients):
    """One pass over recorded purchases and nested exams; no date/payment filter."""
    key = drug_name_key(name)
    history = []
    bought = sold = skipped = 0

    def quantity(item):
        nonlocal skipped
        value = nonnegative_number(item.get('quantity'))
        if value is None or not value.is_integer():
            skipped += 1
            return 0
        return int(value)

    for purchase in purchases:
        for item in purchase.get('drugs', []):
            if not key or drug_name_key(item.get('name')) != key:
                continue
            qty = quantity(item)
            bought += qty
            ppu = nonnegative_number(item.get('ppu'))
            if ppu is None or ppu == 0:
                total = nonnegative_number(item.get('buy_price'))
                ppu = total / qty if total is not None and qty > 0 else None
            history.append({
                'date_buy': purchase.get('date_buy') or '',
                'quantity': item.get('quantity'),
                'buy_price': item.get('buy_price'),
                'ppu': ppu,
                'note': item.get('note', ''),
            })

    for patient in patients:
        for exam in patient.get('exams', []):
            for item in exam.get('drugs', []):
                if key and drug_name_key(item.get('name')) == key:
                    sold += quantity(item)

    history.sort(key=lambda row: row['date_buy'], reverse=True)
    return history, {'bought': bought, 'sold': sold, 'inventory': bought - sold,
                     'skipped': skipped}
