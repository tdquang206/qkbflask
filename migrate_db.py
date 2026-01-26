import os
import json
import shutil
from utils.storage import EncryptedJSONStorage
from dotenv import load_dotenv

load_dotenv()

DB_FILES = ['db.json', 'db_mua_thuoc.json']

def migrate():
    print("Starting migration...")
    
    for filename in DB_FILES:
        if not os.path.exists(filename):
            print(f"Skipping {filename} (not found)")
            continue
            
        print(f"Processing {filename}...")
        
        # 1. Read plain JSON
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                # Check if already encrypted? (Starts with non-bracket usually, but let's assume valid json starts with {)
                content = f.read(1)
                if content != '{':
                    print(f"Warning: {filename} does not start with '{{'. Already encrypted?")
                    f.seek(0)
                    # Verify encryption
                    try:
                        storage_test = EncryptedJSONStorage(filename)
                        storage_test.read()
                        print(f" -> Confirmed already encrypted. Skipping.")
                        continue
                    except:
                        print(" -> Unknown format or corrupted. Skipping to be safe.")
                        continue
                
                f.seek(0)
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {filename} is not valid JSON. Skipping.")
            continue
            
        # 2. Backup
        backup_name = f"{filename}.bak_plain"
        shutil.copy(filename, backup_name)
        print(f" -> Backup created at {backup_name}")
        
        # 3. Encrypt and Write
        try:
            storage = EncryptedJSONStorage(filename)
            storage.write(data)
            print(f" -> Encrypted and written to {filename}")
        except Exception as e:
            print(f" -> Failed to encrypt: {e}")
            # Restore backup
            shutil.copy(backup_name, filename)
            print(" -> Restored backup.")

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
