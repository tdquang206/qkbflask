from tinydb import TinyDB
from utils.storage import EncryptedJSONStorage

# Initialize the database with encrypted storage
db = TinyDB('db.json', storage=EncryptedJSONStorage)

# Define tables
patients_table = db.table('patients')
drugs_table = db.table('drugs')
exams_table = db.table('exams')
users_table = db.table('users')
