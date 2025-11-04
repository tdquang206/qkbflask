Inferred schema from your JSON
# Drugs (per-item)
sku: string

name: string

sell_price: float

buy_price: float

quantity: integer (pack size)

inventory: integer (stock on hand)

# Patients
id: integer (key in top-level map)

name: string

phone: string

address: string

kid_name: string (child/patient display name)

kid_birthday: string (dd/mm/yyyy)

last_visit: string (yyyy-mm-dd)

exams: list of exam objects (see below)

# Exams (embedded in patients or top-level exams)
id: string (UUID when present) or integer (top-level map key)

patient_id: integer

exam_date: string (yyyy-mm-dd)

weight: string/number

height: string/number

history: string

service_fee: string/number (optional)

submit_time: string (optional)

expected_date: string (optional)

drugs: list of drug-prescription objects:

name: string

quantity: string/number

note: string

price: string/number