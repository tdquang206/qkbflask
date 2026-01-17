from tinydb import TinyDB

# Shared database instance with UTF-8 encoding
db = TinyDB('db.json', encoding='utf-8')

# Common tables
patients_table = db.table('patients')
drugs_table = db.table('drugs')
exams_table = db.table('exams')
