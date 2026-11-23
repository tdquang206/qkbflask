"""LAN behavior against disposable encrypted databases and real Flask routes."""
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import zipfile

import pytest
from PIL import Image
from tinydb import TinyDB, Query
from werkzeug.security import generate_password_hash

from utils.coordination import DATA_LOCK, FileTransaction, atomic_write, recover_pending, seal, unseal
from utils.full_backup import create_backup, inspect_backup, restore_backup
from utils.storage import EncryptedJSONStorage

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'synthetic-password-12345'
PASSWORD_HASH = generate_password_hash(PASSWORD)


def synthetic_exam(key, doctor):
    return {'id': key, 'patient_id': 'p', 'exam_date': '2026-10-15',
            'created_by_id': str(doctor), 'created_by_name': f'Doctor {doctor}',
            'department': 'Eye' if doctor == 1 else 'Nutrition', 'history': 'Original',
            'weight': '10', 'height': '100', 'expected_date': '', 'service_fee': '0',
            'total_override': '', 'total_money': 0, 'paid_status': True,
            'submit_time': '261015080000', 'drugs': [], 'services': [],
            'revision': 1, 'legacy_extra': 'keep'}


@pytest.fixture
def lan_app(monkeypatch, tmp_path):
    # conftest already isolates production imports from live clinic storage.
    from app import app
    import shared_db
    modules = {name: importlib.import_module('routes.' + name) for name in
               ('auth', 'core', 'exam', 'patients', 'comparisons', 'admin', 'route_all_exams_page', 'reports', 'drugs', 'mua_thuoc')}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app, 'root_path', str(tmp_path))
    for key, value in {'TESTING': True, 'WTF_CSRF_ENABLED': False, 'DATA_ROOT': str(tmp_path),
                       'DISCORD_ENABLED': False, 'SESSION_COOKIE_SECURE': False}.items():
        monkeypatch.setitem(app.config, key, value)
    databases = [TinyDB(tmp_path / name, storage=EncryptedJSONStorage) for name in
                 ('db.json', 'money_log.json', 'db_services.json', 'db_mua_thuoc.json')]
    db, ledger, services, purchases = databases
    tables = {'patients_table': db.table('patients'), 'users_table': db.table('users'),
              'drugs_table': db.table('drugs'), 'exams_table': db.table('exams'),
              'money_log_table': ledger.table('money_received'),
              'services_table': services.table('services'), 'purchases_table': purchases.table('purchases')}
    for name, table in tables.items():
        monkeypatch.setattr(shared_db, name, table)
    monkeypatch.setattr(shared_db, 'DATABASES', databases)
    monkeypatch.setattr(shared_db, 'db', db)
    bindings = {
        'auth': {'users_table': tables['users_table']},
        'core': {'patients': tables['patients_table'], 'exams': tables['exams_table']},
        'exam': {'Patients_db': tables['patients_table'], 'db': db, 'services_table': tables['services_table']},
        'patients': {'patients': tables['patients_table'], 'services': tables['services_table'], '_APP_ROOT': str(tmp_path)},
        'comparisons': {'patients_table': tables['patients_table']},
        'admin': {'users_table': tables['users_table'], '_ADM_ROOT': str(tmp_path)},
        'route_all_exams_page': {'db': db, 'patients': tables['patients_table'], 'money_log_table': tables['money_log_table']},
    }
    for name, attributes in bindings.items():
        for key, value in attributes.items():
            monkeypatch.setattr(modules[name], key, value)
    for role, username in [('doctor', 'a'), ('doctor', 'b'), ('admin', 'admin'), ('receptionist', 'reception'), ('cashier', 'cashier')]:
        tables['users_table'].insert({'username': username, 'password_hash': PASSWORD_HASH,
                                     'role': role, 'display_name': username, 'department': 'Eye'})
    tables['patients_table'].insert({'id': 'p', 'name': 'Synthetic Patient', 'phone': '000000',
                                     'exams': [synthetic_exam('a', 1), synthetic_exam('b', 2)]})

    def client(user=1):
        value = app.test_client()
        with value.session_transaction() as session:
            session['_user_id'] = str(user)
            session['_fresh'] = True
            session['auth_version'] = '0'
        return value

    yield app, client, tables, tmp_path
    for database in databases:
        database.close()


def exam_form(note='Original', revision=1):
    return {'exam_date': '2026-10-15', 'history': note, 'weight': '10', 'height': '100',
            'expected_date': '', 'service_fee': '0', 'total_override': '', 'exam_revision': str(revision)}


def test_own_edit_history_noop_payment_and_legacy_fields(lan_app):
    _, client, tables, root = lan_app
    c = client()
    assert c.post('/exam/edit_exam/a', data=exam_form()).status_code == 200
    exam = tables['patients_table'].all()[0]['exams'][0]
    assert exam['revision'] == 1 and not exam.get('edit_history')
    response = c.post('/exam/edit_exam/a', data=exam_form('Updated'))
    assert response.status_code == 200 and response.headers['X-Exam-Revision'] == '2'
    exam = tables['patients_table'].all()[0]['exams'][0]
    assert exam['paid_status'] is True and exam['legacy_extra'] == 'keep'
    assert exam['submit_time'] == '261015080000'
    assert exam['edit_history'][0]['before']['history'] == 'Original'
    assert exam['edit_history'][0]['after']['history'] == 'Updated'
    assert exam['edit_history'][0]['actor_id'] == '1'
    assert b'Edited' in c.get('/patient/p/exams').data
    assert b'Updated' in client(2).get('/exam/a/history').data
    assert b'Updated' not in (root / 'db.json').read_bytes()
    assert not (root / '.qkb-journal/pending').exists()


@pytest.mark.parametrize('user', [2, 3, 4])
def test_other_doctor_admin_and_reception_cannot_mutate_exam(lan_app, user):
    _, client, tables, _ = lan_app
    before = copy.deepcopy(tables['patients_table'].all())
    c = client(user)
    for url, method, payload in [('/exam/edit_exam/a', 'post', exam_form('Unauthorized')),
                                 ('/exam/delete_exam/a', 'post', {'exam_revision': '1'}),
                                 ('/exam/p/a/upload_images', 'post', {'exam_revision': '1'})]:
        assert getattr(c, method)(url, data=payload).status_code == 403
    assert c.delete('/exam/p/a/delete_image/a.jpg', headers={'X-Exam-Revision': '1'}).status_code == 403
    assert tables['patients_table'].all() == before


def test_shared_reading_stale_revision_and_immutable_authorship(lan_app):
    _, client, tables, _ = lan_app
    assert client(2).get('/exam/edit_exam/a').status_code == 200
    assert client(4).get('/exam/edit_exam/a').status_code == 403
    c = client()
    assert c.post('/exam/edit_exam/a', data=exam_form('First')).status_code == 200
    assert c.post('/exam/edit_exam/a', data=exam_form('Stale', 1)).status_code == 409
    assert c.post('/exam/edit_exam/a', data={'history': 'No revision'}).status_code == 409
    form = exam_form('Current', 2)
    form['created_by_id'] = '2'
    assert c.post('/exam/edit_exam/a', data=form).status_code == 200
    assert tables['patients_table'].all()[0]['exams'][0]['created_by_id'] == '1'
    assert client(3).post('/admin/edit-exam-info', data={'action': 'save'}).status_code == 403


def test_simultaneous_different_exams_preserve_both(lan_app):
    _, client, tables, _ = lan_app
    barrier = threading.Barrier(2)
    def save(user, key):
        c = client(user)
        barrier.wait(timeout=5)
        return c.post(f'/exam/edit_exam/{key}', data=exam_form(f'Saved {key}')).status_code
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(save, 1, 'a'), pool.submit(save, 2, 'b')]
        assert [f.result(timeout=15) for f in futures] == [200, 200]
    exams = tables['patients_table'].all()[0]['exams']
    assert [e['history'] for e in exams] == ['Saved a', 'Saved b']
    assert all(len(e['edit_history']) == 1 for e in exams)


def test_same_exam_concurrent_saves_have_one_conflict(lan_app):
    _, client, tables, _ = lan_app
    barrier = threading.Barrier(2)
    def save(note):
        c = client()
        barrier.wait(timeout=5)
        return c.post('/exam/edit_exam/a', data=exam_form(note)).status_code
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(save, note) for note in ('One', 'Two')]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]
    assert tables['patients_table'].all()[0]['exams'][0]['revision'] == 2


def test_retried_creation_and_two_departments_same_day(lan_app):
    import uuid
    _, client, tables, _ = lan_app
    c = client()
    form = exam_form('New')
    form.update(submission_id=str(uuid.uuid4()), department='Eye')
    first = c.post('/exam/p/new_exam', data=form)
    second = c.post('/exam/p/new_exam', data=form)
    assert first.status_code == second.status_code == 200
    assert first.json['exam_id'] == second.json['exam_id']
    form.update(submission_id=str(uuid.uuid4()), department='Nutrition')
    third = client(2).post('/exam/p/new_exam', data=form)
    assert third.status_code == 200 and third.json['exam_id'] != first.json['exam_id']
    exams = tables['patients_table'].all()[0]['exams']
    assert len(exams) == 4 and exams[-1]['created_by_id'] == '2'


def test_legacy_missing_owner_is_readonly_and_deletion_retains_history(lan_app):
    _, client, tables, _ = lan_app
    patient = tables['patients_table'].all()[0]
    patient['exams'][0].pop('created_by_id')
    tables['patients_table'].update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
    assert client().post('/exam/edit_exam/a', data=exam_form()).status_code == 403
    c = client(2)
    assert c.post('/exam/delete_exam/b', data={'exam_revision': '1'}).status_code == 200
    exam = tables['patients_table'].all()[0]['exams'][1]
    assert exam['deleted_at'] and exam['edit_history'][0]['before']['history'] == 'Original'
    assert c.get('/exam/b/history').status_code == 200
    assert c.post('/edit_patient/p', data={'action': 'delete'}).status_code == 409


def test_failed_history_write_rolls_back_original_content(lan_app, monkeypatch):
    _, client, tables, _ = lan_app
    table = tables['patients_table']
    original = table.update
    calls = 0
    def fail_history(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('Synthetic full disk during history write')
        return original(*args, **kwargs)
    monkeypatch.setattr(table, 'update', fail_history)
    with pytest.raises(OSError):
        client().post('/exam/edit_exam/a', data=exam_form('Must roll back'))
    assert table.all()[0]['exams'][0]['history'] == 'Original'


def test_encrypted_full_backup_restores_media_ledger_and_history(lan_app):
    _, client, tables, root = lan_app
    assert client().post('/exam/edit_exam/a', data=exam_form('Backed up')).status_code == 200
    media = root / 'uploads/original.txt'
    media.parent.mkdir()
    media.write_text('synthetic sensitive attachment')
    tables['money_log_table'].insert({'exam_id': 'a', 'amount': 123})
    backup = create_backup(root)
    manifest = inspect_backup(backup)
    assert any(e['path'] == 'money_log.json' for e in manifest['entries'])
    assert b'synthetic sensitive attachment' not in backup.read_bytes()
    assert b'Backed up' not in backup.read_bytes()
    media.write_text('changed')
    tables['money_log_table'].truncate()
    restore_backup(root, backup)
    assert media.read_text() == 'synthetic sensitive attachment'
    tables['money_log_table'].clear_cache()
    assert tables['money_log_table'].all()[0]['amount'] == 123
    assert tables['patients_table'].all()[0]['exams'][0]['edit_history']


def test_tampered_backup_fails_before_any_restore_write(lan_app):
    _, _, tables, root = lan_app
    backup = create_backup(root)
    before = (root / 'db.json').read_bytes()
    with zipfile.ZipFile(backup, 'a') as archive:
        manifest = json.loads(unseal(archive.read('manifest.enc')))
        member = next(e['member'] for e in manifest['entries'] if e['path'] == 'db.json')
        with pytest.warns(UserWarning, match='Duplicate name'):
            archive.writestr(member, b'corrupted ciphertext')
    with pytest.raises(ValueError):
        restore_backup(root, backup)
    assert (root / 'db.json').read_bytes() == before


def test_pending_journal_recovers_all_files_after_interruption(tmp_path):
    database = tmp_path / 'db.json'
    ledger = tmp_path / 'money_log.json'
    database.write_bytes(b'original database')
    ledger.write_bytes(b'original ledger')
    transaction = FileTransaction(tmp_path)
    transaction.capture(database)
    transaction.capture(ledger)
    database.write_bytes(b'new database')
    ledger.write_bytes(b'incomplete ledger')
    recover_pending(tmp_path)
    assert database.read_bytes() == b'original database'
    assert ledger.read_bytes() == b'original ledger'


def test_atomic_replacement_failure_preserves_database(tmp_path, monkeypatch):
    path = tmp_path / 'db.json'
    storage = EncryptedJSONStorage(path)
    storage.write({'original': True})
    def fail(*args):
        raise PermissionError('Synthetic replacement failure')
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(PermissionError):
        storage.write({'changed': True})
    assert storage.read() == {'original': True}


def test_existing_empty_database_fails_closed(tmp_path):
    path = tmp_path / 'db.json'
    path.write_bytes(b'')
    with pytest.raises(ValueError):
        EncryptedJSONStorage(path).read()


def test_second_process_cannot_open_same_data_directory(tmp_path):
    from utils.coordination import ensure_single_instance
    ensure_single_instance(tmp_path)
    code = "from utils.coordination import ensure_single_instance; import sys; ensure_single_instance(sys.argv[1])"
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], cwd=ROOT,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and 'Another QKB instance' in result.stderr


def test_log_allowlist_drops_nested_passwords(lan_app):
    _, _, _, root = lan_app
    from utils.db_logger import log_action
    log_action('test', {'form': {'password': 'never-write-this'}, 'token': 'also-secret', 'exam_id': 'a'})
    output = '\n'.join(p.read_text(encoding='utf-8') for p in (root / 'logs').glob('*.log'))
    assert 'never-write-this' not in output and 'also-secret' not in output
    assert '"exam_id": "a"' in output


def test_login_logout_redirect_and_revoked_accounts(lan_app):
    app, client, tables, _ = lan_app
    c = app.test_client()
    response = c.post('/login?next=https://outside.invalid', data={'username': 'a', 'password': PASSWORD})
    assert response.status_code == 302 and response.location == '/'
    assert c.get('/logout').status_code == 405
    assert c.post('/logout').status_code == 302
    c = client()
    tables['users_table'].update({'disabled': True}, doc_ids=[1])
    assert c.post('/exam/edit_exam/a', data=exam_form()).status_code == 401
    c = app.test_client()
    response = c.post('/login', data={'username': 'a', 'password': PASSWORD})
    assert response.status_code == 200
    assert c.post('/exam/edit_exam/a', data=exam_form()).status_code == 401


def test_csrf_is_required_and_admin_backup_is_protected(lan_app, monkeypatch):
    app, client, _, _ = lan_app
    assert client().get('/admin/backups').status_code == 403
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
    assert client().post('/exam/edit_exam/a', data=exam_form()).status_code == 400


def test_payment_retry_and_ledger_failure_rollback(lan_app, monkeypatch):
    _, client, tables, _ = lan_app
    patient = tables['patients_table'].all()[0]
    patient['exams'][0]['paid_status'] = False
    tables['patients_table'].update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
    payload = {'patient_id': 'p', 'exam_id': 'a', 'real_amount': 100, 'desired_status': True}
    assert client().post('/api/mark_paid', json=payload).status_code == 403
    c = client(5)
    original = tables['money_log_table'].insert
    def fail(*args, **kwargs):
        raise OSError('Synthetic ledger failure')
    monkeypatch.setattr(tables['money_log_table'], 'insert', fail)
    assert c.post('/api/mark_paid', json=payload).status_code == 500
    assert tables['patients_table'].all()[0]['exams'][0]['paid_status'] is False
    monkeypatch.setattr(tables['money_log_table'], 'insert', original)
    assert c.post('/api/mark_paid', json=payload).status_code == 200
    assert c.post('/api/mark_paid', json=payload).status_code == 200
    assert len(tables['money_log_table'].all()) == 1


def test_unchanged_package_service_does_not_consume_again(lan_app):
    _, client, tables, _ = lan_app
    patient = tables['patients_table'].all()[0]
    service = {'id': 's', 'name': 'Visit', 'price': 100, 'quantity': 1,
               'note': '', 'prepaid_status': 'PAID PACKAGE'}
    patient['exams'][0].update(services=[service], total_money=100)
    patient['packages'] = [{'service_id': 's', 'remaining_sessions': 4, 'unit_price': 100}]
    tables['patients_table'].update({'exams': patient['exams'], 'packages': patient['packages']}, doc_ids=[patient.doc_id])
    form = exam_form()
    form.update(service_id='s', service_name='Visit', service_price='100', service_quantity='1', service_note='')
    for _ in range(2):
        assert client().post('/exam/edit_exam/a', data=form).status_code == 200
    saved = tables['patients_table'].all()[0]
    assert saved['packages'][0]['remaining_sessions'] == 4
    assert saved['exams'][0]['revision'] == 1


def test_images_are_revision_checked_and_retained_in_history(lan_app):
    _, client, tables, root = lan_app
    image = io.BytesIO()
    Image.new('RGB', (10, 10), 'red').save(image, format='PNG')
    image.seek(0)
    response = client().post('/exam/p/a/upload_images', data={'exam_revision': '1', 'lab_image': (image, 'sample.png')})
    assert response.status_code == 200 and response.headers['X-Exam-Revision'] == '2'
    record = response.json['images'][0]
    path = root / record['path']
    assert path.is_file()
    url = f"/exam/p/a/delete_image/{record['filename']}"
    assert client().delete(url, headers={'X-Exam-Revision': '1'}).status_code == 409
    assert client().delete(url, headers={'X-Exam-Revision': '2'}).status_code == 200
    assert path.is_file()
    history = tables['patients_table'].all()[0]['exams'][0]['edit_history']
    assert history[-1]['before']['images'][0]['filename'] == record['filename']
    assert client(4).get('/uploads/' + record['path'].removeprefix('uploads/')).status_code == 403


def test_full_backup_admin_page_restore_and_session_revocation(lan_app):
    _, client, tables, _ = lan_app
    admin = client(3)
    assert admin.post('/admin/backups').status_code == 302
    page = admin.get('/admin/backups')
    assert page.status_code == 200 and b'.qkb' in page.data
    import re
    filename = re.search(rb'qkb_[0-9TZ]+_[a-f0-9]{8}\.qkb', page.data)[0].decode()
    assert client().post('/exam/edit_exam/a', data=exam_form('After backup')).status_code == 200
    assert admin.post(f'/admin/backups/{filename}/restore', data={'confirmation': 'RESTORE', 'admin_password': PASSWORD}).status_code == 302
    assert tables['patients_table'].all()[0]['exams'][0]['history'] == 'Original'
    assert client().post('/exam/edit_exam/a', data=exam_form()).status_code == 401


def test_password_reset_revokes_sessions_and_cannot_reuse_disabled_username(lan_app):
    app, client, tables, _ = lan_app
    c = client()
    assert client(3).post('/admin/users/reset/a', data={'admin_password': PASSWORD, 'new_password': 'new-synthetic-password'}).status_code == 302
    assert c.post('/exam/edit_exam/a', data=exam_form()).status_code == 401
    sign_in = app.test_client()
    assert sign_in.post('/login', data={'username': 'a', 'password': 'new-synthetic-password'}).location.endswith('/account/password')
    assert sign_in.get('/account/password').status_code == 200
    assert sign_in.post('/account/password', data={'current_password': 'new-synthetic-password', 'new_password': 'final-synthetic-password', 'confirm_password': 'final-synthetic-password'}).status_code == 302
    assert sign_in.get('/exam/edit_exam/a').status_code == 200
    admin = client(3)
    assert admin.post('/admin/users/delete/b').status_code == 302
    assert admin.post('/admin/users/add', data={'username': 'b', 'password': PASSWORD, 'role': 'doctor'}).status_code == 302
    assert len(tables['users_table'].search(Query().username == 'b')) == 1


def test_auth_expiry_keeps_existing_exam_and_returns_json(lan_app):
    import time
    _, client, tables, _ = lan_app
    c = client()
    with c.session_transaction() as session:
        session['authenticated_at'] = time.time() - 9 * 3600
    response = c.post('/exam/edit_exam/a', data=exam_form('Expired'))
    assert response.status_code == 401 and response.is_json
    assert tables['patients_table'].all()[0]['exams'][0]['history'] == 'Original'


def test_incremental_points_reuse_blobs_and_portable_download_is_complete(lan_app):
    _, client, _, root = lan_app
    from utils.full_backup import portable_backup, retain_backups
    media = root / 'uploads' / 'same.txt'
    media.parent.mkdir()
    media.write_text('unchanged attachment')
    first = create_backup(root, incremental=True)
    count = len(list((first.parent / 'blobs').glob('*.enc')))
    second = create_backup(root, incremental=True)
    assert len(list((first.parent / 'blobs').glob('*.enc'))) == count
    inspect_backup(second)
    retain_backups(first.parent)
    with portable_backup(second) as stream:
        portable = root / 'portable.qkb'
        portable.write_bytes(stream.read())
    manifest = inspect_backup(portable)
    assert manifest['external_blobs'] is False
    media.write_text('changed')
    restore_backup(root, portable)
    assert media.read_text() == 'unchanged attachment'
    response = client(3).get('/admin/backups/' + first.name)
    assert response.status_code == 200
    downloaded = root / 'download.qkb'
    downloaded.write_bytes(response.data)
    assert inspect_backup(downloaded)['external_blobs'] is False


def test_ten_doctors_save_independent_exams_without_losses(lan_app):
    _, client, tables, _ = lan_app
    patient = tables['patients_table'].all()[0]
    assignments = []
    for index in range(10):
        user = tables['users_table'].insert({'username': f'trial-{index}', 'role': 'doctor', 'password_hash': PASSWORD_HASH})
        key = f'exam-{index}'
        patient['exams'].append(synthetic_exam(key, user))
        assignments.append((user, key))
    tables['patients_table'].update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
    barrier = threading.Barrier(10)
    def save(assignment):
        user, key = assignment
        c = client(user)
        barrier.wait(timeout=10)
        return c.post('/exam/edit_exam/' + key, data=exam_form('Saved ' + key)).status_code
    with ThreadPoolExecutor(10) as pool:
        assert list(pool.map(save, assignments)) == [200] * 10
    saved = tables['patients_table'].all()[0]['exams'][2:]
    assert all(exam['history'] == 'Saved ' + exam['id'] and len(exam['edit_history']) == 1 for exam in saved)


def test_offline_restore_tool_on_spare_directory(lan_app):
    _, _, _, root = lan_app
    backup = create_backup(root)
    spare = root / 'spare'
    command = [sys.executable, str(ROOT / 'tools/restore_backup.py'), str(backup), '--data-dir', str(spare)]
    verified = subprocess.run(command + ['--verify-only'], capture_output=True, text=True, timeout=15)
    assert verified.returncode == 0 and not spare.exists()
    restored = subprocess.run(command + ['--confirm'], capture_output=True, text=True, timeout=15)
    assert restored.returncode == 0, restored.stderr
    assert json.loads(unseal((spare / 'db.json').read_bytes()))['patients']['1']['id'] == 'p'


def test_no_rollback_after_commit_marker_when_cleanup_is_interrupted(tmp_path, monkeypatch):
    path = tmp_path / 'db.json'
    path.write_bytes(b'old')
    transaction = FileTransaction(tmp_path)
    transaction.capture(path)
    path.write_bytes(b'committed')
    def fail():
        raise OSError('Synthetic cleanup failure')
    monkeypatch.setattr(transaction, 'cleanup', fail)
    with pytest.raises(OSError):
        transaction.finish(True)
    recover_pending(tmp_path)
    assert path.read_bytes() == b'committed'


def test_retry_with_changed_creation_content_is_a_conflict(lan_app):
    import uuid
    _, client, tables, _ = lan_app
    form = exam_form('Original new exam')
    form['submission_id'] = str(uuid.uuid4())
    c = client()
    assert c.post('/exam/p/new_exam', data=form).status_code == 200
    form['history'] = 'Different draft'
    assert c.post('/exam/p/new_exam', data=form).status_code == 409
    assert tables['patients_table'].all()[0]['exams'][-1]['history'] == 'Original new exam'


def test_legacy_package_ambiguity_preserves_note_and_balances(lan_app):
    _, client, tables, _ = lan_app
    patient = tables['patients_table'].all()[0]
    patient['exams'][0].update(services=[{'id': 's', 'name': 'Visit', 'price': 100, 'quantity': 1,
                                        'note': '', 'prepaid_status': 'PAID PACKAGE'}], total_money=100)
    patient['packages'] = [{'id': 'old', 'service_id': 's', 'remaining_sessions': 4, 'unit_price': 100},
                           {'id': 'new', 'service_id': 's', 'remaining_sessions': 5, 'unit_price': 100}]
    tables['patients_table'].update({'exams': patient['exams'], 'packages': patient['packages']}, doc_ids=[patient.doc_id])
    form = exam_form()
    form.update(service_id='s', service_name='Visit', service_price='100', service_quantity='1', service_note='')
    c = client()
    assert c.post('/exam/edit_exam/a', data=form).status_code == 200
    assert tables['patients_table'].all()[0]['packages'] == patient['packages']


    form['service_quantity'] = '2'
    assert c.post('/exam/edit_exam/a', data=form).status_code == 409
    assert tables['patients_table'].all()[0]['packages'] == patient['packages']


def test_retention_removes_only_expired_points_and_unreferenced_blobs(lan_app):
    from datetime import datetime, timedelta, timezone
    from utils.full_backup import retain_backups
    _, _, _, root = lan_app
    media = root / 'uploads' / 'changing.txt'
    media.parent.mkdir()
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    points = []
    for day in range(45):
        media.write_text(f'synthetic version {day}')
        path = create_backup(root, incremental=True)
        manifest = inspect_backup(path)
        manifest['created_at'] = (now - timedelta(days=day)).isoformat()
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.enc', seal(json.dumps(manifest).encode()))
        points.append(path)
    retain_backups(points[0].parent, now=now)
    assert all(path.exists() for path in points[:30])
    assert all(not path.exists() for path in points[30:])
    for path in points[:30]:
        inspect_backup(path)
