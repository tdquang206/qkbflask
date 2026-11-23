"""Build and encrypt the minimal drug catalog used by the standalone calculator."""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timezone

from Crypto.Cipher import AES

from utils.drug_values import drug_name_key, nonnegative_number

CATALOG_FORMAT = 'qkb-drug-catalog-encrypted'
CATALOG_VERSION = 1
KDF_ITERATIONS = 600_000
AAD = b'qkb-drug-catalog:v1'


def build_drug_catalog(drugs, purchases):
    """Return only name, sell price, cost price, and catalog update metadata."""
    latest_costs = {}
    ordered_purchases = sorted(
        purchases,
        key=lambda purchase: str(purchase.get('date_buy') or ''),
        reverse=True,
    )
    for purchase in ordered_purchases:
        for item in purchase.get('drugs', []):
            name = str(item.get('name') or '').strip()
            key = drug_name_key(name)
            if not name or key in latest_costs:
                continue
            ppu = nonnegative_number(item.get('ppu'))
            if ppu:
                latest_costs[key] = ppu

    items = []
    for drug in drugs:
        name = str(drug.get('name') or '').strip()
        if not name:
            continue
        sell_raw = drug.get('sell_price')
        cost_raw = latest_costs.get(drug_name_key(name), drug.get('buy_price'))
        sell = 0 if sell_raw in (None, '') else nonnegative_number(sell_raw)
        cost = 0 if cost_raw in (None, '') else nonnegative_number(cost_raw)
        if sell is None or cost is None:
            raise ValueError('A drug has an invalid sell or cost price; correct it before exporting.')
        items.append({'name': name, 'sell': sell, 'cost': cost})

    items.sort(key=lambda item: item['name'].casefold())
    return {
        'schema_version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'items': items,
    }


def encrypt_drug_catalog(catalog, password):
    """Encrypt a catalog using PBKDF2-HMAC-SHA256 and AES-256-GCM."""
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError('Use a catalog password of at least 12 characters.')

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, KDF_ITERATIONS, dklen=32)
    plaintext = json.dumps(
        catalog, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
    cipher.update(AAD)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)

    return {
        'format': CATALOG_FORMAT,
        'version': CATALOG_VERSION,
        'kdf': 'PBKDF2-HMAC-SHA256',
        'iterations': KDF_ITERATIONS,
        'cipher': 'AES-256-GCM',
        'salt': base64.b64encode(salt).decode('ascii'),
        'nonce': base64.b64encode(nonce).decode('ascii'),
        'ciphertext': base64.b64encode(ciphertext + tag).decode('ascii'),
    }


def encrypted_catalog_json(catalog, password):
    """Serialize an encrypted catalog for manual upload to Cloudflare R2."""
    return json.dumps(
        encrypt_drug_catalog(catalog, password),
        ensure_ascii=False,
        indent=2,
    ) + '\n'
