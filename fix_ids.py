import json
import uuid

def fix_duplicate_ids():
    with open('db.json', 'r', encoding='utf-8') as f:
        db = json.load(f)

    patients = db.get('patients', {})
    all_ids = set()
    fixed_count = 0

    for p_id, patient in patients.items():
        exams = patient.get('exams', [])
        for exam in exams:
            exam_id = exam.get('id')
            if not exam_id or exam_id in all_ids:
                new_id = str(uuid.uuid4())
                print(f"Fixing duplicate/missing ID for patient {p_id}: {exam_id} -> {new_id}")
                exam['id'] = new_id
                fixed_count += 1
                all_ids.add(new_id)
            else:
                all_ids.add(exam_id)

    if fixed_count > 0:
        with open('db.json', 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"Finished. Fixed {fixed_count} duplicate IDs.")
    else:
        print("No duplicate IDs found.")

if __name__ == "__main__":
    fix_duplicate_ids()
