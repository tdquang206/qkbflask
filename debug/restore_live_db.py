# debug/restore_live_db.py
import os
import shutil
import sys
from dotenv import load_dotenv
from tinydb import TinyDB

# Load environment variables
load_dotenv(encoding='utf-8')

# Ensure we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.storage import EncryptedJSONStorage

def restore_db():
    live_db_path = 'db.json'
    backup_db_path = 'backups/db_backup_2026_21.json'
    corrupted_backup_path = 'backups/db_corrupted_pre_restore.json'

    if not os.path.exists(backup_db_path):
        print(f"Error: Backup file not found at {backup_db_path}")
        return

    # 1. Back up current live db as a safety measure
    if os.path.exists(live_db_path):
        shutil.copy2(live_db_path, corrupted_backup_path)
        print(f"Safety backup of current live database created at: {corrupted_backup_path}")

    # 2. Overwrite live db with week 21 backup
    shutil.copy2(backup_db_path, live_db_path)
    print(f"Successfully restored live database from backup: {backup_db_path}")

    # 3. Verify restored users
    key = os.getenv("DB_ENCRYPTION_KEY")
    if not key:
        print("Warning: DB_ENCRYPTION_KEY is not set. Cannot verify.")
        return

    db = TinyDB(live_db_path, storage=EncryptedJSONStorage)
    users_table = db.table('users')
    users = users_table.all()
    print("\n--- Restored Users Verification ---")
    print(f"Total restored users: {len(users)}")
    for u in users:
        print(f"Username: {u.get('username')}, Role: {u.get('role')}, Display: {u.get('display_name')}")

    patients_table = db.table('patients')
    print(f"Total restored patients: {len(patients_table.all())}")

if __name__ == "__main__":
    restore_db()
