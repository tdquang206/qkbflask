import copy
import hashlib
import importlib.util
import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest
from flask import Flask, render_template
from flask_login import LoginManager, UserMixin
from flask_wtf.csrf import CSRFProtect, generate_csrf
from PIL import Image
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from utils.grading import MMASI, assess, calculate_mmasi
from utils.image_comparison import (gallery_images, image_id, image_index, image_is_referenced,
                                    safe_image_path, transform_image, validate_transform)

ROOT = Path(__file__).resolve().parents[1]


def observations(area=6, darkness=4):
    return {r['id']: {'area': area, 'darkness': darkness} for r in MMASI['regions']}


@pytest.fixture
def comparison_app(monkeypatch, tmp_path):
    database = TinyDB(storage=MemoryStorage)
    table = database.table('patients')
    shared = types.ModuleType('shared_db')
    shared.patients_table = table
    shared.db = database
    shared.services_table = database.table('services')
    monkeypatch.setitem(sys.modules, 'shared_db', shared)
    spec = importlib.util.spec_from_file_location('isolated_comparisons', ROOT / 'routes/comparisons.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = Flask(__name__, root_path=str(tmp_path), template_folder=str(ROOT / 'templates'),
                static_folder=str(ROOT / 'static'))
    app.config.update(TESTING=True, SECRET_KEY='test-only-comparison-secret')
    CSRFProtect(app)
    login = LoginManager(app)

    class User(UserMixin):
        id = 'test-user'
        display_name = 'Test Clinician'
        username = 'test'
        role = 'doctor'

    login.user_loader(lambda key: User() if key == 'test-user' else None)
    app.register_blueprint(module.comparisons_bp)
    app.add_url_rule('/csrf', 'csrf', lambda: generate_csrf())
    for endpoint in ('settings.discord_settings', 'settings.departments_settings',
                     'settings.services_management', 'settings.manage_template', 'auth.logout',
                     'exam.new_exam', 'exam.edit_exam', 'exam.delete_exam'):
        app.add_url_rule('/stub/' + endpoint, endpoint, lambda: '')
    patient = {'id': 'patient-one', 'name': 'Synthetic Patient', 'phone': '0000000000', 'exams': []}
    for i in range(2):
        folder = tmp_path / 'uploads' / 'patient_image' / '0000000000'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'original_{i}.jpg'
        image = Image.new('RGB', (32, 16))
        image.putdata([(x * 7, y * 10, 75 + i * 20) for y in range(16) for x in range(32)])
        image.save(path)
        patient['exams'].append({'id': f'exam-{i}', 'exam_date': f'2026-0{i+1}-01',
                                 'history': 'Existing clinical note', 'drugs': [],
                                 'images': [{'filename': path.name, 'path': path.relative_to(tmp_path).as_posix()}]})
    table.insert(patient)
    table.insert({'id': 'another-patient', 'exams': []})

    @app.route('/history')
    def history():
        p = table.all()[0]
        return render_template('previous_exams.html', patient=p, exams=p['exams'], comparison_image_id=image_id, comparison_gallery=gallery_images)

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = 'test-user'
        session['_fresh'] = True
    token = client.get('/csrf').get_data(as_text=True)
    headers = {'X-CSRFToken': token}
    yield client, table, headers, tmp_path, app
    database.close()


def session_payload(client):
    catalog = client.get('/patient/patient-one/comparisons').get_json()
    images = [i for i in catalog['images'] if i['kind'] == 'original']
    return {'revision': catalog['revision'],
            'images': [{'image_id': i['id'], 'transform': {'brightness': .1, 'contrast': 1.1}} for i in images],
            'reference_image_id': images[0]['id'], 'baseline_exam_id': images[0]['exam_id'],
            'target_exam_id': 'exam-1', 'assessments': {
                'exam-0': {'method': 'mmasi', 'version': 1, 'inputs': observations(), 'view': 'original', 'reviewed': True},
                'exam-1': {'method': 'mmasi', 'version': 1, 'inputs': observations(3, 2), 'view': 'original', 'reviewed': True},
            }, 'comment': 'Synthetic follow-up', 'save_copies': False, 'save_sheet': False, 'append_note': False}


def test_grading_formula_missing_and_confirmation():
    assert calculate_mmasi(observations())[1] == 24
    assert calculate_mmasi(observations(0, 0))[1] == 0
    values = observations(0, 0)
    values['chin'] = {'area': 6, 'darkness': 4}
    assert calculate_mmasi(values)[1] == 2.4
    values.pop('forehead')
    assert calculate_mmasi(values)[1] is None
    rating = assess({'method': 'mmasi', 'version': 1, 'inputs': observations(), 'score': 999})
    assert rating['score'] == 24 and rating['status'] == 'incomplete'


@pytest.mark.parametrize('bad', [-1, 7, 1.5, True, '2'])
def test_invalid_clinical_inputs_rejected(bad):
    values = observations()
    values['forehead']['area'] = bad
    with pytest.raises(ValueError):
        calculate_mmasi(values)


def test_catalog_does_not_mutate_legacy_images_and_history_renders(comparison_app):
    client, table, _, _, _ = comparison_app
    before = copy.deepcopy(table.all())
    catalog = client.get('/patient/patient-one/comparisons').get_json()
    assert len(catalog['images']) == 2 and catalog['methods'][0]['id'] == 'mmasi'
    assert table.all() == before
    page = client.get('/history')
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert 'data-image-id=' in text and 'comparison.js' in text
    assert 'Chọn ảnh' in text and 'Ch?n ?nh' not in text


def test_save_versions_reopen_notes_archive_and_original_integrity(comparison_app):
    client, table, headers, root, _ = comparison_app
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('original*.jpg')}
    body = session_payload(client)
    body.update(save_copies=True, save_sheet=True, append_note=True)
    preview = client.post('/patient/patient-one/comparisons/summary', json=body, headers=headers)
    assert preview.status_code == 200
    assert '24/24' in preview.json['summary'] and '6/24' in preview.json['summary']
    assert '-18' in preview.json['summary']
    first = client.post('/patient/patient-one/comparisons', json=body, headers=headers)
    assert first.status_code == 201
    record = first.json['record']
    assert len(record['derived_image_ids']) == 3
    assert record['author_id'] == 'test-user'
    saved = table.all()[0]
    assert saved['exams'][1]['history'].startswith('Existing clinical note\n\n')
    assert saved['exams'][1]['comparisons'][0]['summary'] == preview.json['summary']
    assert all(image.get('id') for e in saved['exams'] for image in e['images'])
    assert len(list(root.rglob('*_edited_01.jpg'))) == 2
    catalog = client.get('/patient/patient-one/comparisons').json
    assert catalog['records'][0]['images'] == record['images']
    body['revision'] = catalog['revision']
    assert client.post('/patient/patient-one/comparisons', json=body, headers=headers).status_code == 201
    assert len(list(root.rglob('*_edited_02.jpg'))) == 2
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in originals.items())
    archive = client.get(f"/patient/patient-one/comparisons/{record['id']}/download")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.data)) as package:
        manifest = json.loads(package.read('comparison.json'))
        assert len(manifest['files']) == 5 and manifest['missing'] == []
    html = client.get('/history').get_data(as_text=True)
    assert 'Đã hiệu chỉnh' in html and 'Mở lại' in html


def test_metadata_only_no_file_writes_and_empty_grading_remains_incomplete(comparison_app):
    client, table, headers, root, _ = comparison_app
    body = session_payload(client)
    body['assessments']['exam-1']['inputs'] = {}
    before = sorted(str(p) for p in root.rglob('*.jpg'))
    response = client.post('/patient/patient-one/comparisons', json=body, headers=headers)
    assert response.status_code == 201
    assert response.json['record']['assessments']['exam-1']['score'] is None
    assert sorted(str(p) for p in root.rglob('*.jpg')) == before
    assert table.all()[0]['exams'][1]['history'] == 'Existing clinical note'


@pytest.mark.parametrize('change', [
    {'reference_image_id': 'foreign'}, {'baseline_exam_id': 'foreign'},
    {'target_exam_id': 'foreign'}, {'images': []}, {'assessments': {'foreign': {}}},
])
def test_invalid_ownership_and_payload_leave_data_unchanged(comparison_app, change):
    client, table, headers, _, _ = comparison_app
    body = session_payload(client)
    body.update(change)
    before = copy.deepcopy(table.all())
    assert client.post('/patient/patient-one/comparisons', json=body, headers=headers).status_code == 400
    assert table.all() == before


def test_stale_revision_csrf_auth_and_cross_patient_isolation(comparison_app):
    client, table, headers, _, app = comparison_app
    body = session_payload(client)
    assert client.post('/patient/patient-one/comparisons', json=body).status_code == 400
    anonymous = app.test_client()
    assert anonymous.get('/patient/patient-one/comparisons').status_code == 401
    catalog = client.get('/patient/another-patient/comparisons').json
    assert catalog['images'] == [] and catalog['records'] == []
    body['revision'] = catalog['revision']
    assert client.post('/patient/another-patient/comparisons', json=body, headers=headers).status_code == 400
    body['revision'] = 'stale'
    assert client.post('/patient/patient-one/comparisons', json=body, headers=headers).status_code == 409
    assert not table.all()[0]['exams'][1].get('comparisons')


def test_source_ids_survive_rename_and_deletion_references(comparison_app):
    client, table, headers, root, _ = comparison_app
    body = session_payload(client)
    body['save_copies'] = True
    saved = client.post('/patient/patient-one/comparisons', json=body, headers=headers).json['record']
    patient = table.all()[0]
    index = image_index(patient)
    source_id = body['images'][0]['image_id']
    exam, image = index[source_id]
    assert image_is_referenced(patient, exam, image)
    old_path = safe_image_path(root, image)
    new_path = old_path.with_name('renamed.jpg')
    old_path.rename(new_path)
    image.update(filename=new_path.name, path=new_path.relative_to(root).as_posix())
    table.update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
    assert image_id(exam, image) == source_id
    catalog = client.get('/patient/patient-one/comparisons').json
    assert any(i['id'] == source_id and i['filename'] == 'renamed.jpg' for i in catalog['images'])
    assert client.post(f"/patient/patient-one/comparisons/{saved['id']}/delete", json={}, headers=headers).status_code == 200
    patient = table.all()[0]
    assert patient['exams'][1]['comparisons'] == []
    assert image_is_referenced(patient, exam, image)  # Edited copies still need their original.


def test_failed_write_removes_only_new_derivatives(comparison_app, monkeypatch):
    client, table, headers, root, _ = comparison_app
    body = session_payload(client)
    body.update(save_copies=True, save_sheet=True)
    def fail(*args, **kwargs):
        raise OSError('synthetic write failure')
    monkeypatch.setattr(table, 'update', fail)
    response = client.post('/patient/patient-one/comparisons', json=body, headers=headers)
    assert response.status_code == 400
    assert len(list(root.rglob('*.jpg'))) == 2
    assert not table.all()[0]['exams'][1].get('comparisons')


def test_transform_identity_crop_bounds_and_path_safety(tmp_path):
    folder = tmp_path / 'uploads'
    folder.mkdir()
    path = folder / 'source.png'
    Image.new('RGB', (20, 10), (150, 100, 50)).save(path)
    identity = transform_image(path, validate_transform({}))
    assert identity.getpixel((0, 0)) == (150, 100, 50)
    edited = transform_image(path, validate_transform({'brightness': .1, 'contrast': 1.1, 'crop': [0, 0, .5, .5]}))
    assert edited.size == (10, 5) and edited.getpixel((0, 0)) == (178, 123, 68)
    with pytest.raises(ValueError):
        validate_transform({'brightness': float('nan')})
    with pytest.raises(ValueError):
        validate_transform({'crop': [0.9, 0, .5, 1]})
    outside = tmp_path / 'private.png'
    Image.new('RGB', (2, 2)).save(outside)
    with pytest.raises(ValueError):
        safe_image_path(tmp_path, {'path': str(outside)})


def test_existing_exam_routes_preserve_comparisons_and_guard_sources(comparison_app, monkeypatch):
    client, table, headers, root, app = comparison_app
    # Import the actual exam module without production settings/database startup.
    settings = types.ModuleType('routes.settings')
    settings.load_settings = lambda: {}
    monkeypatch.setitem(sys.modules, 'routes.settings', settings)
    spec = importlib.util.spec_from_file_location('isolated_exam_lifecycle', ROOT / 'routes/exam.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'delete_exam_files', lambda *args: None)
    body = session_payload(client)
    body['save_copies'] = True
    assert client.post('/patient/patient-one/comparisons', json=body, headers=headers).status_code == 201
    before = table.all()[0]
    saved_records = copy.deepcopy(before['exams'][1]['comparisons'])
    with app.test_request_context('/exam/edit_exam/exam-1', method='POST', data={
            'exam_date': '2026-02-02', 'history': 'Updated clinical note'}):
        response = module.edit_exam('exam-1')
        assert response.status_code == 200
    patient = table.all()[0]
    assert patient['exams'][1]['comparisons'] == saved_records
    assert patient['exams'][1]['images'] == before['exams'][1]['images']
    with app.test_request_context('/delete', method='DELETE'):
        response, status = module.delete_exam_image('patient-one', 'exam-0', 'original_0.jpg')
        assert status == 409
    with app.test_request_context('/delete', method='POST'):
        response, status = module.delete_exam('exam-0')
        assert status == 409


def test_phone_rename_preserves_saved_ids_and_edited_filenames(comparison_app, monkeypatch):
    client, table, headers, root, _ = comparison_app
    spec = importlib.util.spec_from_file_location('isolated_patient_rename', ROOT / 'routes/patients.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attr, value in [('_APP_ROOT', root), ('_PATIENT_IMAGE_ROOT', root / 'uploads/patient_image'),
                        ('_PDF_ROOT', root / 'files/pdf'), ('_JPEG_ROOT', root / 'files/jpeg')]:
        monkeypatch.setattr(module, attr, str(value))
    body = session_payload(client)
    body['save_copies'] = True
    assert client.post('/patient/patient-one/comparisons', json=body, headers=headers).status_code == 201
    patient = table.all()[0]
    before_ids = set(image_index(patient))
    edited = [copy.deepcopy(i) for e in patient['exams'] for i in e['images'] if i.get('kind') == 'adjusted']
    module._rename_patient_assets(patient, '0000000000', '1111111111')
    assert set(image_index(patient)) == before_ids
    assert all(safe_image_path(root, image).is_file() for _, image in image_index(patient).values())
    assert [i for e in patient['exams'] for i in e['images'] if i.get('kind') == 'adjusted'] == edited
