
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_db import patients_table
from tinydb import Query

print("Checking patients for IDs...")
all_patients = patients_table.all()
count_total = len(all_patients)
count_missing_id = 0
count_with_id = 0

for p in all_patients:
    if 'id' not in p or not p['id']:
        print(f"Patient missing ID: {p.get('name')} (doc_id: {p.doc_id})")
        count_missing_id += 1
    else:
        # print(f"Patient OK: {p.get('name')} - {p.get('id')}")
        count_with_id += 1

print(f"Total: {count_total}")
print(f"With ID: {count_with_id}")
print(f"Missing ID: {count_missing_id}")
