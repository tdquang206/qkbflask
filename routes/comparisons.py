"""Patient-scoped comparison records. Pixels are always derived from owned sources."""

import copy
import io
import json
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from PIL import Image, ImageDraw, ImageOps
from tinydb import Query

from shared_db import patients_table
from utils.grading import GRADING_METHODS, assess
from utils.image_comparison import (MAX_IMAGES, TRANSFORM_VERSION, image_index,
                                    revision, safe_image_path, save_version,
                                    transform_image, validate_transform)

comparisons_bp = Blueprint('comparisons', __name__)
_save_lock = threading.RLock()


def get_patient(patient_id):
    patient = patients_table.get(Query().id == patient_id)
    if patient is None:
        from flask import abort
        abort(404)
    return copy.deepcopy(patient)


def app_root():
    return Path(current_app.root_path).resolve()


@comparisons_bp.route('/patient/<patient_id>/comparisons', methods=['GET'])
@login_required
def catalog(patient_id):
    patient = get_patient(patient_id)
    index = image_index(patient)
    images = [{'id': key, 'exam_id': exam['id'], 'date': exam.get('exam_date', ''),
               'filename': image.get('filename', ''), 'kind': image.get('kind', 'original'),
               'source_image_id': image.get('source_image_id'),
               'url': '/uploads/' + safe_image_path(app_root(), image).relative_to(app_root() / 'uploads').as_posix()}
              for key, (exam, image) in index.items()
              if _exists(image)]
    return jsonify(revision=revision(patient), images=images,
                   exams=[{'id': e['id'], 'date': e.get('exam_date', '')} for e in patient.get('exams', [])],
                   records=[c for e in patient.get('exams', []) for c in e.get('comparisons', [])],
                   methods=[method[0] for method in GRADING_METHODS.values()])


def _exists(image):
    try:
        safe_image_path(app_root(), image)
        return True
    except ValueError:
        return False


def validate_session(patient, body):
    if not isinstance(body, dict):
        raise ValueError('Dữ liệu so sánh không hợp lệ.')
    index = image_index(patient, assign=True)
    exams = {exam['id']: exam for exam in patient.get('exams', [])}
    selected = body.get('images')
    if not isinstance(selected, list) or not 1 <= len(selected) <= MAX_IMAGES:
        raise ValueError(f'Chọn từ 1 đến {MAX_IMAGES} ảnh.')
    items, seen, exam_ids = [], set(), set()
    for item in selected:
        if not isinstance(item, dict) or not isinstance(item.get('image_id'), str) or item.get('image_id') not in index:
            raise ValueError('Ảnh không thuộc bệnh nhân hoặc đã bị xóa.')
        key = item['image_id']
        exam, image = index[key]
        if key in seen or image.get('kind', 'original') != 'original':
            raise ValueError('Chọn ảnh gốc, mỗi ảnh một lần.')
        safe_image_path(app_root(), image)
        seen.add(key)
        exam_ids.add(exam['id'])
        items.append({'image_id': key, 'exam_id': exam['id'],
                      'transform': validate_transform(item.get('transform', {}))})
    if not isinstance(body.get('reference_image_id'), str) or body.get('reference_image_id') not in seen:
        raise ValueError('Chọn ảnh chuẩn trong các ảnh đã chọn.')
    if (not isinstance(body.get('baseline_exam_id'), str) or not isinstance(body.get('target_exam_id'), str)
            or body.get('baseline_exam_id') not in exam_ids or body.get('target_exam_id') not in exams):
        raise ValueError('Lần khám mốc hoặc lần khám lưu không hợp lệ.')
    ratings = body.get('assessments', {})
    if not isinstance(ratings, dict) or any(key not in exam_ids for key in ratings):
        raise ValueError('Đánh giá không thuộc các lần khám đã chọn.')
    ratings = {key: assess(value) for key, value in ratings.items()}
    comment = body.get('comment', '')
    if not isinstance(comment, str) or len(comment) > 4000:
        raise ValueError('Ghi chú tối đa 4000 ký tự.')
    record = {'schema_version': 1, 'transform_version': TRANSFORM_VERSION,
              'images': items, 'reference_image_id': body['reference_image_id'],
              'baseline_exam_id': body['baseline_exam_id'], 'target_exam_id': body['target_exam_id'],
              'assessments': ratings, 'comment': comment.strip()}
    return record, index, exams


def summary(record, exams):
    lines = ['So sánh ảnh — mốc: ' + exams[record['baseline_exam_id']].get('exam_date', '')]
    lines.append('Ảnh hiệu chỉnh chỉ hỗ trợ quan sát; đánh giá do bác sĩ nhập.')
    baseline = record['assessments'].get(record['baseline_exam_id'])
    for key, rating in record['assessments'].items():
        value = f"{rating['score']:g}/24" if rating['status'] == 'complete' else 'chưa hoàn tất'
        view = 'ảnh gốc' if rating['view'] == 'original' else 'ảnh đã chỉnh'
        line = f"{exams[key].get('exam_date', '')}: mMASI {value} ({view})"
        if (baseline and key != record['baseline_exam_id'] and baseline['status'] == 'complete'
                and rating['status'] == 'complete' and rating['view'] == baseline['view']):
            delta = round(rating['score'] - baseline['score'], 2)
            line += f'; thay đổi {delta:+g}'
        lines.append(line)
    if record['comment']:
        lines.append(record['comment'])
    return '\n'.join(lines)


@comparisons_bp.route('/patient/<patient_id>/comparisons/summary', methods=['POST'])
@login_required
def preview_summary(patient_id):
    try:
        record, _, exams = validate_session(get_patient(patient_id), request.get_json(silent=True))
        return jsonify(summary=summary(record, exams))
    except ValueError as error:
        return jsonify(message=str(error)), 400


@comparisons_bp.route('/patient/<patient_id>/comparisons', methods=['POST'])
@login_required
def save_comparison(patient_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(message='Dữ liệu không hợp lệ.'), 400
    written = []
    committed = False
    try:
        with _save_lock:
            patient = get_patient(patient_id)
            if body.get('revision') != revision(patient):
                return jsonify(message='Lịch sử đã thay đổi. Mở lại trang trước khi lưu.'), 409
            record, index, exams = validate_session(patient, body)
            record.update(id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc).isoformat(),
                          author_id=str(current_user.get_id()),
                          author=str(getattr(current_user, 'display_name', None) or getattr(current_user, 'username', '')))
            record['summary'] = summary(record, exams)
            record['derived_image_ids'] = []
            target = exams[record['target_exam_id']]
            if target.get('images') is None:
                target['images'] = []
            # Dedicated patient folder; source filenames are kept for recognizable versions.
            folder = app_root() / 'uploads' / 'comparisons' / str(uuid.uuid5(uuid.NAMESPACE_URL, patient_id))
            folder = folder.resolve()
            if not folder.is_relative_to(app_root() / 'uploads' / 'comparisons'):
                raise ValueError('Thư mục lưu ảnh không hợp lệ.')
            tiles = []
            for item in record['images']:
                source_exam, original = index[item['image_id']]
                path = safe_image_path(app_root(), original)
                if body.get('save_copies') is True or body.get('save_sheet') is True:
                    adjusted = transform_image(path, item['transform'])
                    if body.get('save_copies') is True:
                        destination, version = save_version(adjusted, folder, path.stem, 'edited')
                        written.append(destination)
                        attachment = {'id': str(uuid.uuid4()), 'filename': destination.name,
                                      'path': destination.relative_to(app_root()).as_posix(), 'kind': 'adjusted',
                                      'source_image_id': item['image_id'], 'comparison_id': record['id'],
                                      'source_filename': path.name,
                                      'edit_version': version, 'reference_image_id': record['reference_image_id'],
                                      'transform': item['transform'], 'transform_version': TRANSFORM_VERSION,
                                      'created_at': record['created_at'], 'author_id': record['author_id']}
                        target.setdefault('images', []).append(attachment)
                        record['derived_image_ids'].append(attachment['id'])
                    if body.get('save_sheet') is True:
                        tile = Image.new('RGB', (600, 670), '#ffffff')
                        thumbnail = ImageOps.contain(adjusted, (580, 590))
                        tile.paste(thumbnail, ((600 - thumbnail.width) // 2, 35))
                        draw = ImageDraw.Draw(tile)
                        draw.text((12, 10), f"{source_exam.get('exam_date', '')} | Adjusted", fill='black')
                        rating = record['assessments'].get(source_exam['id'])
                        label = 'mMASI: not assessed'
                        if rating:
                            label = f"mMASI: {rating['score'] if rating['status'] == 'complete' else 'incomplete'} ({rating['view']})"
                        draw.text((12, 635), label, fill='black')
                        tiles.append(tile)
            if tiles:
                cols = min(2, len(tiles))
                sheet = Image.new('RGB', (600 * cols, 670 * ((len(tiles) + cols - 1) // cols)), 'white')
                for i, tile in enumerate(tiles):
                    sheet.paste(tile, ((i % cols) * 600, (i // cols) * 670))
                path, _ = save_version(sheet, folder, f"comparison_{record['id'][:8]}", 'sheet')
                written.append(path)
                attachment = {'id': str(uuid.uuid4()), 'filename': path.name,
                              'path': path.relative_to(app_root()).as_posix(), 'kind': 'comparison_sheet',
                              'comparison_id': record['id']}
                target.setdefault('images', []).append(attachment)
                record['derived_image_ids'].append(attachment['id'])
            if body.get('append_note') is True:
                target['history'] = (target.get('history') or '').rstrip() + '\n\n' + record['summary']
            target.setdefault('comparisons', []).append(record)
            # Detect edits made through other routes while image generation was running.
            if revision(get_patient(patient_id)) != body['revision']:
                return jsonify(message='Lịch sử đã thay đổi trong lúc lưu. Mở lại trang.'), 409
            patients_table.update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
            committed = True
            return jsonify(record=record, revision=revision(patient)), 201
    except ValueError as error:
        return jsonify(message=str(error)), 400
    except (OSError, Image.DecompressionBombError):
        current_app.logger.exception('Comparison save failed')
        return jsonify(message='Không thể lưu. Kiểm tra ảnh nguồn và dữ liệu chấm điểm.'), 400
    finally:
        if not committed:
            for path in written:
                if path.resolve().is_relative_to(app_root() / 'uploads' / 'comparisons'):
                    path.unlink(missing_ok=True)


@comparisons_bp.route('/patient/<patient_id>/comparisons/<comparison_id>/download')
@login_required
def download_comparison(patient_id, comparison_id):
    patient = get_patient(patient_id)
    record = next((c for e in patient.get('exams', []) for c in e.get('comparisons', [])
                   if c.get('id') == comparison_id), None)
    if not record:
        return jsonify(message='Không tìm thấy so sánh.'), 404
    index = image_index(patient)
    keys = [i['image_id'] for i in record['images']] + record.get('derived_image_ids', [])
    archive = io.BytesIO()
    manifest = {'comparison': record, 'files': [], 'missing': []}
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as package:
        for key in dict.fromkeys(keys):
            if key not in index or not _exists(index[key][1]):
                manifest['missing'].append(key)
                continue
            path = safe_image_path(app_root(), index[key][1])
            name = f'images/{key}/{path.name}'
            package.write(path, name)
            manifest['files'].append({'image_id': key, 'archive_path': name, 'exam_id': index[key][0]['id']})
        package.writestr('comparison.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    archive.seek(0)
    return send_file(archive, mimetype='application/zip', as_attachment=True,
                     download_name=f'comparison_{comparison_id}.zip')


@comparisons_bp.route('/patient/<patient_id>/comparisons/<comparison_id>/delete', methods=['POST'])
@login_required
def delete_comparison(patient_id, comparison_id):
    with _save_lock:
        patient = get_patient(patient_id)
        for exam in patient.get('exams', []):
            records = exam.get('comparisons', [])
            if any(c.get('id') == comparison_id for c in records):
                exam['comparisons'] = [c for c in records if c.get('id') != comparison_id]
                patients_table.update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
                return jsonify(message='Đã xóa bản so sánh. Ảnh đính kèm và ghi chú được giữ lại.')
        return jsonify(message='Không tìm thấy bản so sánh.'), 404
