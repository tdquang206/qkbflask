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
