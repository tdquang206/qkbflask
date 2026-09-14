"""Versioned grading registry. Clinical observations are entered by the clinician.

mMASI: https://jamanetwork.com/journals/jamadermatology/fullarticle/2519450
Validation: https://pubmed.ncbi.nlm.nih.gov/20398960/
"""

MMASI = {
    'id': 'mmasi', 'version': 1, 'label': 'mMASI', 'maximum': 24,
    'regions': [
        {'id': 'forehead', 'label': 'Trán', 'weight': 0.3},
        {'id': 'right_malar', 'label': 'Má phải của bệnh nhân', 'weight': 0.3},
        {'id': 'left_malar', 'label': 'Má trái của bệnh nhân', 'weight': 0.3},
        {'id': 'chin', 'label': 'Cằm', 'weight': 0.1},
    ],
    'fields': [
        {'id': 'area', 'label': 'Diện tích (A)', 'options': [
            '0 — Không có', '1 — >0 đến <10%', '2 — 10–29%', '3 — 30–49%',
            '4 — 50–69%', '5 — 70–89%', '6 — 90–100%',
        ]},
        {'id': 'darkness', 'label': 'Độ sậm (D)', 'options': [
            '0 — Không có', '1 — Rất nhẹ', '2 — Nhẹ', '3 — Rõ', '4 — Nặng',
        ]},
    ],
    'formula': '0.3 × A × D (trán + má phải + má trái) + 0.1 × A × D (cằm)',
    'source': 'https://jamanetwork.com/journals/jamadermatology/fullarticle/2519450',
}


def calculate_mmasi(observations):
    clean, complete, total = {}, True, 0
    if not isinstance(observations, dict):
        raise ValueError('Quan sát mMASI không hợp lệ.')
    for region in MMASI['regions']:
        values = observations.get(region['id'], {})
        if not isinstance(values, dict):
            raise ValueError('Vùng mMASI không hợp lệ.')
        clean[region['id']] = {}
        for field, maximum in (('area', 6), ('darkness', 4)):
            value = values.get(field)
            if value in (None, ''):
                value = None
                complete = False
            elif type(value) is not int or not 0 <= value <= maximum:
                raise ValueError('Điểm mMASI ngoài phạm vi.')
            clean[region['id']][field] = value
        a, d = clean[region['id']].values()
        if a is not None and d is not None:
            total += region['weight'] * a * d
    return clean, round(total, 2) if complete else None


GRADING_METHODS = {'mmasi': (MMASI, calculate_mmasi)}


def assess(payload):
    if not isinstance(payload, dict):
        raise ValueError('Đánh giá không hợp lệ.')
    method_id = payload.get('method')
    method = GRADING_METHODS.get(method_id) if isinstance(method_id, str) else None
    if not method or type(payload.get('version')) is not int or payload.get('version') != method[0]['version']:
        raise ValueError('Phương pháp hoặc phiên bản chấm điểm không hỗ trợ.')
    view = payload.get('view', 'original')
    if view not in ('original', 'adjusted'):
        raise ValueError('Chọn ảnh gốc hoặc ảnh đã chỉnh để chấm điểm.')
    inputs, score = method[1](payload.get('inputs', {}))
    reviewed = payload.get('reviewed') is True
    return {'method': method[0]['id'], 'version': method[0]['version'],
            'view': view, 'inputs': inputs, 'score': score,
            'reviewed': reviewed,
            'status': 'complete' if score is not None and reviewed else 'incomplete'}
