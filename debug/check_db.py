import os
import json
from dotenv import load_dotenv
from tinydb import TinyDB, Query

# Load environment variables
load_dotenv()

# We need the encryption key from .env to read the database
# The EncryptedJSONStorage class is in utils.storage
from utils.storage import EncryptedJSONStorage
from shared_db import patients_table

def debug_db():
    print("Checking patients table...")
    patients = patients_table.all()
    print(f"Total patients: {len(patients)}")
    if patients:
        p = patients[0]
        print(f"Sample patient: {p.get('name')} (ID: {p.get('id')})")
        exams = p.get('exams', [])
        print(f"Total exams for this patient: {len(exams)}")
        if exams:
            print(f"Sample exam ID: {exams[0].get('id')}")

if __name__ == "__main__":
    debug_db()
