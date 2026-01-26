from tinydb import TinyDB

# Shared database instance with UTF-8 encoding
# Shared database instance with UTF-8 encoding
from utils.storage import EncryptedJSONStorage
db = TinyDB('db.json', storage=EncryptedJSONStorage)

# Common tables
patients_table = db.table('patients')
drugs_table = db.table('drugs')
exams_table = db.table('exams')
users_table = db.table('users')
