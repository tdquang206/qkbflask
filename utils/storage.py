import os
import json
import base64
from tinydb.storages import Storage
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

class EncryptedJSONStorage(Storage):
    def __init__(self, filename, **kwargs):
        self.filename = filename
        
        key_b64 = os.getenv('DB_ENCRYPTION_KEY')
        if not key_b64:
             raise ValueError("DB_ENCRYPTION_KEY environment variable is not set.")
        
        try:
            self.key = base64.b64decode(key_b64)
        except Exception as e:
            raise ValueError(f"Invalid DB_ENCRYPTION_KEY: {e}")

    def read(self):
        if not os.path.exists(self.filename):
            return None

        with open(self.filename, 'rb') as f:
            data = f.read()

        if not data:
            return None
            
        try:
            # Structure: Nonce (16) + Tag (16) + Ciphertext
            if len(data) < 32:
                # Fallback: maybe it's plain JSON? (Optional support during migration debugging)
                # But strict security says fail.
                # However, if migration hasn't run, this will crash app. 
                # Let's try to detect matching json structure first simply? No.
                # Just assume encrypted.
                raise ValueError("Data corrupted or not encrypted")
            
            nonce = data[:16]
            tag = data[16:32]
            ciphertext = data[32:]
            
            cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
            decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
            
            return json.loads(decrypted_data.decode('utf-8'))
            
        except (ValueError, KeyError) as e:
            # Decryption failed
            print(f"Decryption failed for {self.filename}: {e}")
            raise e

    def write(self, data):
        json_data = json.dumps(data).encode('utf-8')
        
        cipher = AES.new(self.key, AES.MODE_GCM) # Auto-generates nonce (16 bytes by default in newer PyCryptoDome? No usually 16)
        # AES GCM standard nonce is 12 bytes (96 bits) generally, but PyCryptodome default might be 16.
        # Let's check docs or be explicit. PyCryptodome GCM default nonce is 16 bytes.
        
        ciphertext, tag = cipher.encrypt_and_digest(json_data)
        
        with open(self.filename, 'wb') as f:
            f.write(cipher.nonce + tag + ciphertext)

    def close(self):
        pass

def get_encryption_key():
    """Get the encryption key from environment variable"""
    key_b64 = os.getenv('DB_ENCRYPTION_KEY')
    if not key_b64:
        raise ValueError("DB_ENCRYPTION_KEY environment variable is not set.")
    try:
        return base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(f"Invalid DB_ENCRYPTION_KEY: {e}")


def decrypt_file(encrypted_file_path):
    """
    Decrypt an encrypted JSON file and return the decrypted data
    
    Args:
        encrypted_file_path: Path to the encrypted JSON file
        
    Returns:
        dict: Decrypted JSON data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If decryption fails
    """
    if not os.path.exists(encrypted_file_path):
        raise FileNotFoundError(f"File not found: {encrypted_file_path}")
    
    key = get_encryption_key()
    
    with open(encrypted_file_path, 'rb') as f:
        data = f.read()
    
    if not data:
        raise ValueError("File is empty")
    
    if len(data) < 32:
        raise ValueError("File is corrupted or not encrypted")
    
    try:
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]
        
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
        
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


def get_json_database_files(root_dir="."):
    """
    Get all JSON files in the root directory that are databases
    Excludes files already in backups/ folder
    
    Args:
        root_dir: Root directory to search in (default current directory)
        
    Returns:
        list: List of tuples (filename, filepath) for JSON database files
    """
    json_files = []
    
    # Look for .json files in root directory
    for filename in os.listdir(root_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(root_dir, filename)
            # Skip backup files and decrypted exports
            if os.path.isfile(filepath) and not filename.startswith('decrypted_'):
                json_files.append((filename, filepath))
    
    return sorted(json_files)


def export_decrypted_databases(root_dir=".", exports_dir="decrypted_exports"):
    """
    Decrypt all JSON database files and save decrypted versions
    
    Args:
        root_dir: Root directory where JSON files are located
        exports_dir: Directory to save decrypted files (relative to root)
        
    Returns:
        dict: {
            'success': list of exported files,
            'errors': list of (filename, error_message) tuples,
            'export_dir': path to exports directory
        }
    """
    # Create exports directory if it doesn't exist
    export_path = os.path.join(root_dir, exports_dir)
    os.makedirs(export_path, exist_ok=True)
    
    json_files = get_json_database_files(root_dir)
    result = {
        'success': [],
        'errors': [],
        'export_dir': export_path
    }
    
    for filename, filepath in json_files:
        try:
            # Decrypt the file
            decrypted_data = decrypt_file(filepath)
            
            # Save decrypted version with a prefix
            export_filename = f"decrypted_{filename}"
            export_filepath = os.path.join(export_path, export_filename)
            
            with open(export_filepath, 'w', encoding='utf-8') as f:
                json.dump(decrypted_data, f, indent=2, ensure_ascii=False)
            
            result['success'].append({
                'filename': export_filename,
                'original_filename': filename,
                'size': os.path.getsize(export_filepath)
            })
        except Exception as e:
            result['errors'].append((filename, str(e)))
    
    return result