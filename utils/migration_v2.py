import sys
import os
from dotenv import load_dotenv

# Add parent directory to path so we can import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from tinydb import TinyDB, Query
from utils.storage import EncryptedJSONStorage

def migrate():
    # Path to main DB
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.json')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    print(f"Opening database at {db_path}...")
    try:
        db = TinyDB(db_path, storage=EncryptedJSONStorage)
        patients_table = db.table('patients')
        
        updated_count = 0
        patients = patients_table.all()
        
        try:
            users_table = db.table('users')
            User = Query()
            hue_account = users_table.search(User.username == 'hue')
            
            if hue_account:
                hue_data = hue_account[0]
                hue_id = hue_data.get('id', hue_account[0].doc_id)
                hue_name = hue_data.get('display_name', 'BS. Hue')
                print(f"Found user 'hue': ID={hue_id}, Name={hue_name}")
            else:
                hue_id = 'unknown'
                hue_name = 'BS. Hue' # Fallback as requested
                print("User 'hue' not found, using fallback values.")

        except Exception as e:
             print(f"Error fetching user hue: {e}")
             hue_id = 'unknown'
             hue_name = 'BS. Hue'

        for patient in patients:
            exams = patient.get('exams', [])
            patient_updated = False
            
            for exam in exams:
                exam_changed = False
                # Migration: Force update all exams to "PK Nhi" regardless of current value,
                # as per user request to set all existing exams to "PK Nhi"
                if exam.get('department') != 'PK Nhi':
                    exam['department'] = 'PK Nhi'
                    exam_changed = True
                
                # Assign to 'hue'
                if exam.get('created_by_name') != hue_name:
                    exam['created_by_name'] = hue_name
                    exam['created_by_id'] = str(hue_id)
                    exam_changed = True
                    
                if exam_changed:
                    patient_updated = True
            
            if patient_updated:
                patients_table.update({'exams': exams}, doc_ids=[patient.doc_id])
                updated_count += 1
                
        print(f"Migration complete. Updated {updated_count} patients.")
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
