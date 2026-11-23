"""Clinical ownership and encrypted, append-only exam revisions."""
import copy
from datetime import datetime, timezone

from flask import abort, request
from flask_login import current_user

META = {'revision', 'edit_history', 'edited_at', 'edited_by_id', 'edited_by_name'}


def can_edit_exam(exam):
    return (current_user.is_authenticated
            and getattr(current_user, 'role', None) in ('doctor', 'admin')
            and exam.get('created_by_id') is not None
            and str(exam['created_by_id']) == str(current_user.id)
            and not exam.get('deleted_at'))


def require_owner(exam, check_revision=True):
    if not can_edit_exam(exam):
        abort(403, description='Chỉ bác sĩ tạo lần khám mới được sửa. Hồ sơ cũ chưa xác định chủ sở hữu chỉ được đọc.')
    if check_revision:
        body = request.get_json(silent=True) if request.is_json else request.form
        supplied = request.headers.get('X-Exam-Revision') or (body or {}).get('exam_revision')
        if str(supplied) != str(exam.get('revision', 1)):
            abort(409, description='Hồ sơ đã thay đổi hoặc thiếu phiên bản. Giữ lại nội dung đang nhập và mở lại hồ sơ để đối chiếu.')


def clinical_snapshot(exam):
    # Payment is an independent, separately authorized workflow.
    return copy.deepcopy({key: value for key, value in exam.items()
                          if key not in META and key not in {'paid_status', 'payment_revision', 'last_payment_request_id'}})


def record_edit(before, after):
    previous, updated = clinical_snapshot(before), clinical_snapshot(after)
    after['revision'] = before.get('revision', 1)
    after['edit_history'] = copy.deepcopy(before.get('edit_history', []))
    if previous == updated:
        for key in ('edited_at', 'edited_by_id', 'edited_by_name'):
            if key in before:
                after[key] = before[key]
        return False
    now = datetime.now(timezone.utc).isoformat()
    actor_id = str(current_user.id)
    actor_name = getattr(current_user, 'display_name', current_user.id)
    after['revision'] += 1
    after.update(edited_at=now, edited_by_id=actor_id, edited_by_name=actor_name)
    after['edit_history'].append({
        'revision': after['revision'], 'at': now, 'actor_id': actor_id,
        'actor_name': actor_name, 'before': previous, 'after': updated,
        'fields': sorted(k for k in previous.keys() | updated.keys() if previous.get(k) != updated.get(k)),
    })
    return True


def finish_exam_change(table, before, patient_id, response):
    """Called before request commit: content and history share the rollback journal."""
    if before is None or response.status_code >= 400:
        return response
    from tinydb import Query
    patient = table.get(Query().id == patient_id)
    if patient:
        after = next((e for e in patient.get('exams', []) if e.get('id') == before['id']), None)
        if after is not None:
            changed = record_edit(before, after)
            if changed:
                table.update({'exams': patient['exams']}, doc_ids=[patient.doc_id])
            response.headers['X-Exam-Revision'] = str(after.get('revision', 1))
            payload = response.get_json(silent=True) if response.is_json else None
            if isinstance(payload, dict) and 'record' in payload and 'revision' in payload:
                import json
                from utils.image_comparison import revision
                payload['revision'] = revision(patient)
                response.set_data(json.dumps(payload, ensure_ascii=False))
    return response
