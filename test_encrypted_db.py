#!/usr/bin/env python
# Test script to verify encrypted database access works correctly

from tinydb import TinyDB
from utils.storage import EncryptedJSONStorage

try:
    print("Testing encrypted database access...")
    purchases_db = TinyDB('db_mua_thuoc.json', storage=EncryptedJSONStorage)
    purchases_table = purchases_db.table('purchases')
    all_purchases = purchases_table.all()
    print(f"✓ Successfully read {len(all_purchases)} purchases from encrypted database")
    print("✓ Encryption/decryption working correctly!")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
