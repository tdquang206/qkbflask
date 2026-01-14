Project Summary: QKBFlask
This is a Flask-based Clinic/Pharmacy Management System, likely tailored for a pediatric clinic (references to "kid_name"). It uses TinyDB for data storage (JSON files).

# Key Features:
Patient Management: Track patient details (name, birthdate, address) and history.
Exam/Visit Management:
Create and edit exams/visits.
Prescribe drugs during exams.
PDF Generation: Generates prescriptions/receipts using wkhtmltopdf.
Lab Images: Upload and store patient lab results/images.
Drug Inventory:
Manage drug list, buy/sell prices, and inventory quantity.
Purchases (Mua Thuoc): dedicated module to track incoming drug supplies and costs.
Drug Sold Reports: specific reporting on drug consumption.
Data & Backup:
Stores data in db.json (patients, drugs, exams) and db_mua_thuoc.json (purchases).
Automatic weekly backups.
Technical Stack:
Backend: Python, Flask
Database: TinyDB (JSON)
Frontend: Jinja2 Templates (HTML/CSS/JS), Bootstrap (inferred).
Utilities: wkhtmltopdf (PDFs), Pillow (Image processing), rapidfuzz (Fuzzy search for drugs).