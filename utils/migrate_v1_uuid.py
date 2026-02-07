
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared_db import db, patients_table
import uuid
import shutil
from datetime import datetime

def migrate():
    print("Starting migration...")
    
    # 1. Backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join("backups", f"db_pre_uuid_{timestamp}.json")
    os.makedirs("backups", exist_ok=True)
    
    if os.path.exists("db.json"):
        shutil.copy("db.json", backup_path)
        print(f"Backup created at {backup_path}")
    else:
        print("No db.json found!")
        return

    # 2. Iterate and Update
    all_patients = patients_table.all()
    updated_count = 0
    
    for patient in all_patients:
        needs_save = False
        
        # Add ID if missing
        if 'id' not in patient:
            patient['id'] = str(uuid.uuid4())
            needs_save = True
            
        # Check nested exams for patient_id (if they store it)
        # In current logic, exams are inside 'exams' list.
        # usually they don't store parent ID redundantly, but let's check
        if 'exams' in patient:
            for exam in patient['exams']:
                if 'patient_id' not in exam or exam['patient_id'] != patient['id']:
                     exam['patient_id'] = patient['id']
                     needs_save = True
        
        if needs_save:
            # We use doc_id to update the specific record
            patients_table.update(patient, doc_ids=[patient.doc_id])
            updated_count += 1
            print(f"Updated patient: {patient.get('name')} -> {patient['id']}")

    print(f"Migration complete. Updated {updated_count} patients.")

if __name__ == "__main__":
    migrate()
