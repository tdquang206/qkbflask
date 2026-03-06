from tinydb import TinyDB
from utils.storage import EncryptedJSONStorage

# Initialize the primary application database with encrypted storage
# this file contains patients, exams, drugs, users, etc.
db = TinyDB('db.json', storage=EncryptedJSONStorage)

# If you want to keep the accounting log completely isolated from the
# main dataset we create a second TinyDB instance pointing at a different
# file but using the same encryption helper.  This allows reports to be
# generated and files to be rotated independently.

# Separate ledger that will hold actual money received entries.  It is
# encrypted just like the main database.
ledger_db = TinyDB('money_log.json', storage=EncryptedJSONStorage)

# Separate database for services management (Khoa / Dịch vụ)
# Encrypted like the main database
services_db = TinyDB('db_services.json', storage=EncryptedJSONStorage)

# Define tables for the main database
patients_table = db.table('patients')
drugs_table = db.table('drugs')
exams_table = db.table('exams')
users_table = db.table('users')

# Define a convenience table alias for the ledger entries.
# ``money_log_table`` will be used by the route when recording receipts.
money_log_table = ledger_db.table('money_received')

# Define table for services
services_table = services_db.table('services')
