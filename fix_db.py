import json

with open('db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

patients = db['patients']

# Delete exam from patient 38
if '29' in patients:
    exams_38 = patients['29'].get('exams', [])
    exams_38_cleaned = [e for e in exams_38 if e['id'] != '99dcb620-98bd-49ab-b891-8622eab54947']
    patients['29']['exams'] = exams_38_cleaned
    print(f"✅ Removed exam from patient 29")
    print(f"   Before: {len(exams_38)} exams → After: {len(exams_38_cleaned)} exams")
    
    # If patient 29 is now empty (only had this exam), consider deleting it
    if not patients['29']['exams']:
        print(f"⚠️  Patient 29 now has 0 exams - consider deleting this patient")

# Fix patient_id in patient 38's exam
if '38' in patients:
    for exam in patients['38'].get('exams', []):
        if exam['id'] == '99dcb620-98bd-49ab-b891-8622eab54947':
            old_pid = exam['patient_id']
            exam['patient_id'] = 38
            print(f"\n✅ Fixed exam in patient 38")
            print(f"   patient_id: {old_pid} → 38")

# Save
with open('db.json', 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("\n✅ Database fixed!")
print(f"Patient 38: {len(patients['38']['exams'])} exams")
print(f"Patient 29: {len(patients['38']['exams'])} exams")