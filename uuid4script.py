from tinydb import TinyDB
from uuid import uuid4

# open your DB file (adjust path if needed)
db = TinyDB("db.json")
patients = db.table("patients")

migrated_count = 0

for patient in patients.all():
    exams = patient.get("exams", [])
    changed = False

    for exam in exams:
        if "id" not in exam:
            exam["id"] = str(uuid4())
            changed = True

    if changed:
        patients.update({"exams": exams}, doc_ids=[patient.doc_id])
        migrated_count += 1

print(f"Migration complete. Updated {migrated_count} patient records.")