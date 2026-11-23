import base64
import hashlib
import json

import pytest
from Crypto.Cipher import AES

from utils.drug_catalog import (
    AAD,
    CATALOG_FORMAT,
    KDF_ITERATIONS,
    build_drug_catalog,
    encrypt_drug_catalog,
)


def decrypt_envelope(envelope, password):
    salt = base64.b64decode(envelope['salt'])
    nonce = base64.b64decode(envelope['nonce'])
    encrypted = base64.b64decode(envelope['ciphertext'])
    key = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, KDF_ITERATIONS, dklen=32)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
    cipher.update(AAD)
    plaintext, tag = encrypted[:-16], encrypted[-16:]
    return json.loads(cipher.decrypt_and_verify(plaintext, tag).decode('utf-8'))


def test_catalog_contains_only_current_sell_and_latest_cost():
    catalog = build_drug_catalog(
        [
            {'name': 'Drug B', 'sell_price': 20, 'buy_price': 10, 'quantity': 8},
            {'name': 'Drug A', 'sell_price': 30.5, 'buy_price': 12},
            {'name': '   ', 'sell_price': 1, 'buy_price': 1},
        ],
        [
            {'date_buy': '2026-02-01', 'drugs': [{'name': 'Drug A', 'ppu': 14}]},
            {'date_buy': '2026-01-01', 'drugs': [{'name': 'Drug A', 'ppu': 11}]},
        ],
    )

    assert [item['name'] for item in catalog['items']] == ['Drug A', 'Drug B']
    assert catalog['items'][0] == {'name': 'Drug A', 'sell': 30.5, 'cost': 14}
    assert catalog['items'][1] == {'name': 'Drug B', 'sell': 20, 'cost': 10}
    assert set(catalog) == {'schema_version', 'updated_at', 'items'}


def test_encrypted_catalog_round_trips_without_exposing_plaintext():
    catalog = {
        'schema_version': 1,
        'updated_at': '2026-11-18T00:00:00Z',
        'items': [{'name': 'Secret Drug Name', 'sell': 12.5, 'cost': 8}],
    }

    envelope = encrypt_drug_catalog(catalog, 'test catalog passphrase')
    encoded = json.dumps(envelope)

    assert envelope['format'] == CATALOG_FORMAT
    assert 'Secret Drug Name' not in encoded
    assert decrypt_envelope(envelope, 'test catalog passphrase') == catalog


def test_encrypted_catalog_rejects_wrong_password_and_tampering():
    envelope = encrypt_drug_catalog(
        {'schema_version': 1, 'updated_at': 'now', 'items': []},
        'test catalog passphrase',
    )
    with pytest.raises(ValueError):
        decrypt_envelope(envelope, 'wrong catalog passphrase')

    tampered = bytearray(base64.b64decode(envelope['ciphertext']))
    tampered[0] ^= 1
    envelope['ciphertext'] = base64.b64encode(tampered).decode('ascii')
    with pytest.raises(ValueError):
        decrypt_envelope(envelope, 'test catalog passphrase')


def test_catalog_export_rejects_invalid_price():
    with pytest.raises(ValueError, match='invalid sell or cost price'):
        build_drug_catalog([{'name': 'Drug A', 'sell_price': 'NaN'}], [])
