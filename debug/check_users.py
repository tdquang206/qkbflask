# debug/check_users.py
import os
import sys
from dotenv import load_dotenv
from tinydb import TinyDB, Query

# Load environment variables
load_dotenv(encoding='utf-8')

# Ensure we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.storage import EncryptedJSONStorage

def check_users():
    # Read live users
    key = os.getenv("DB_ENCRYPTION_KEY")
    if not key:
        print("Error: DB_ENCRYPTION_KEY is not set.")
        return

    db = TinyDB('db.json', storage=EncryptedJSONStorage)
    users_table = db.table('users')
    users = users_table.all()
    print("--- Live Users ---")
    print(f"Total live users: {len(users)}")
    for u in users:
        print(f"Username: {u.get('username')}, Role: {u.get('role')}, Display: {u.get('display_name')}")

    # Read latest backup
    backup_path = 'backups/db_backup_2026_21.json'
    if os.path.exists(backup_path):
        print("\n--- Backup Users (from db_backup_2026_21.json) ---")
        backup_db = TinyDB(backup_path, storage=EncryptedJSONStorage)
        backup_users_table = backup_db.table('users')
        backup_users = backup_users_table.all()
        print(f"Total backup users: {len(backup_users)}")
        for u in backup_users:
             print(f"Username: {u.get('username')}, Role: {u.get('role')}, Display: {u.get('display_name')}")
    else:
        print(f"\nNo backup file found at {backup_path}")

if __name__ == "__main__":
    check_users()
