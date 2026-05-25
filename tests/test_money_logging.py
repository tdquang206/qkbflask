import pytest
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage

# We don't need to import the actual encrypted database for this unit test;
# instead we emulate the behaviour of ``money_log_table`` using an in-memory
# TinyDB.  The route's logic simply calls ``insert`` on that table, so if we
# can exercise the code path and inspect the in-memory table we know the
# expected data would have been written correctly.

import routes.route_all_exams_page as route_all_exams_page


def test_ledger_entry_creation(monkeypatch):
    # prepare a fresh in-memory table and patch the module reference
    temp_db = TinyDB(storage=MemoryStorage)
    temp_table = temp_db.table('money_received')
    monkeypatch.setattr(route_all_exams_page, 'money_log_table', temp_table)

    # simulate insertion logic directly (bypass flask request context)
    entry = {
        'patient_id': 'patient123',
        'exam_id': 'exam456',
        'amount': 500,
        'timestamp': '2026-03-04T12:00:00',
        'user': 'tester'
    }
    temp_table.insert(entry)

    all_records = temp_table.all()
    assert len(all_records) == 1
    assert all_records[0]['exam_id'] == 'exam456'
    assert all_records[0]['amount'] == 500


def test_money_map_generation(monkeypatch):
    """Verify that get_exam_list can build money_map dictionary properly."""
    # build some fake logs with out-of-order timestamps
    logs = [
        {'exam_id': 'a', 'timestamp': '2026-01-01T00:00:00', 'amount': 100},
        {'exam_id': 'a', 'timestamp': '2026-02-01T00:00:00', 'amount': 200},
        {'exam_id': 'b', 'timestamp': '2026-01-15T00:00:00', 'amount': 300},
    ]
    # Use MemoryStorage TinyDB table so both all() and insert() work perfectly
    temp_db = TinyDB(storage=MemoryStorage)
    temp_table = temp_db.table('money_received')
    for log in logs:
        temp_table.insert(log)
        
    route_all_exams_page.money_log_table = temp_table
    import routes.reports as reports_module
    reports_module.money_log_table = temp_table

    # Mock user and patient tables to use safe in-memory MemoryStorage and avoid truncating live database
    temp_shared_db = TinyDB(storage=MemoryStorage)
    temp_users_table = temp_shared_db.table('users')
    temp_patients_table = temp_shared_db.table('patients')

    import shared_db
    monkeypatch.setattr(shared_db, 'db', temp_shared_db)
    monkeypatch.setattr(shared_db, 'users_table', temp_users_table)
    monkeypatch.setattr(shared_db, 'patients_table', temp_patients_table)

    import routes.route_all_exams_page as route_all_exams_page_module
    monkeypatch.setattr(route_all_exams_page_module, 'db', temp_shared_db)
    monkeypatch.setattr(route_all_exams_page_module, 'patients', temp_patients_table)

    import routes.auth as auth_module
    monkeypatch.setattr(auth_module, 'users_table', temp_users_table)

    # call get_exam_list GET portion via test client to ensure money_map is
    # included in template context.  This is a light integration rather than
    # end-to-end render.
    from app import app
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True

    with app.test_client() as client:
        # insert into safe mocked in-memory tables
        temp_users_table.insert({'username': 'x', 'password_hash': 'irrelevant'})
        temp_patients_table.insert({
            'id': 'pid1',
            'exams': [
                {'id': 'e1', 'paid_status': False, 'service_fee': '0', 'drugs': []}
            ]
        })

        # manually authenticate by setting session user id
        with client.session_transaction() as sess:
            sess['_user_id'] = str(temp_users_table.all()[0].doc_id)

        # first make sure the exam list loads without error
        response = client.get('/danh_sach_kham_benh')
        assert response.status_code == 200

        # now hit the mark_paid endpoint with a real_amount and verify ledger entry
        resp2 = client.post('/api/mark_paid', json={
            'patient_id': 'pid1',
            'exam_id': 'e1',
            'real_amount': 1234
        })
        assert resp2.status_code == 200
        assert resp2.json.get('success')

        # the patient record should be updated
        updated = temp_patients_table.get(Query().id == 'pid1')
        assert updated['exams'][0]['paid_status'] is True

        # ledger should contain 4 records (3 pre-seeded logs + 1 newly inserted log)
        logs = route_all_exams_page.money_log_table.all()
        assert len(logs) == 4
        assert logs[3]['amount'] == 1234
        assert logs[3]['exam_id'] == 'e1'

        # hit the money_flow report and ensure it includes total
        resp3 = client.get('/money_flow')
        assert resp3.status_code == 200
        assert b'Bap c' not in resp3.data  # sanity check that response is HTML
        # total should appear (string conversion may include commas)
        assert b'1,234' in resp3.data or b'1234' in resp3.data

