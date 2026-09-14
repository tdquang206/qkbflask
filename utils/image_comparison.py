"""Non-destructive image processing and stable references for exam comparisons."""

import hashlib
import json
import math
import uuid
from pathlib import Path

from PIL import Image, ImageOps

TRANSFORM_VERSION = 1
MAX_IMAGES = 8


def image_id(exam, image):
    return image.get('id') or str(uuid.uuid5(
        uuid.NAMESPACE_URL, f"qkb:{exam['id']}:{image.get('path', '')}:{image.get('filename', '')}"))


def image_index(patient, assign=False):
    index = {}
    for exam in patient.get('exams', []):
        for image in exam.get('images', []) or []:
            key = image_id(exam, image)
            if key in index:
                raise ValueError('Mã ảnh trùng nhau. Cần kiểm tra dữ liệu ảnh.')
            if assign:
                image['id'] = key
            index[key] = (exam, image)
    return index


def revision(patient):
    return hashlib.sha256(json.dumps(patient.get('exams', []), ensure_ascii=False,
                                     sort_keys=True).encode('utf-8')).hexdigest()


def referenced_images(patient):
    keys = set()
    for exam in patient.get('exams', []):
        for comparison in exam.get('comparisons', []):
            keys.update(item['image_id'] for item in comparison.get('images', []))
            keys.update(comparison.get('derived_image_ids', []))
    return keys


def image_is_referenced(patient, exam, image):
    key = image_id(exam, image)
    return key in referenced_images(patient) or any(
        record.get('source_image_id') == key
        for _, record in image_index(patient).values())


def gallery_images(exam):
    """Place copies beside their source when both are attached to the same visit."""
    images = exam.get('images', []) or []
    children = {}
    for image in images:
        if image.get('source_image_id'):
            children.setdefault(image['source_image_id'], []).append(image)
    ordered, included = [], set()
    for image in images:
        if image.get('kind', 'original') == 'original':
            ordered.append(image)
            included.add(image_id(exam, image))
            for child in children.get(image_id(exam, image), []):
                ordered.append(child)
                included.add(image_id(exam, child))
    ordered.extend(image for image in images if image_id(exam, image) not in included)
    return ordered


def safe_image_path(root, image):
    root = Path(root).resolve()
    path = Path(str(image.get('path', '')).replace('\\', '/'))
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(root / 'uploads') or not path.is_file():
        raise ValueError('Không tìm thấy ảnh nguồn trong thư mục uploads.')
    return path


def validate_transform(data):
    if not isinstance(data, dict):
        raise ValueError('Thông số chỉnh ảnh không hợp lệ.')
    result = {}
    for name, default, lower, upper in (('brightness', 0, -0.3, 0.3),
                                        ('contrast', 1, 0.5, 1.5)):
        value = data.get(name, default)
        if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError('Thông số sáng/tương phản ngoài phạm vi.')
        result[name] = value
    for name in ('crop', 'patch'):
        rect = data.get(name)
        if rect is not None:
            if (not isinstance(rect, list) or len(rect) != 4 or
                    any(type(x) not in (int, float) or not math.isfinite(x) for x in rect)):
                raise ValueError('Vùng chọn không hợp lệ.')
            x, y, w, h = rect
            if min(x, y) < 0 or min(w, h) < 0.01 or x + w > 1.000001 or y + h > 1.000001:
                raise ValueError('Vùng chọn nằm ngoài ảnh.')
        result[name] = rect
    return result


def transform_image(path, settings):
    with Image.open(path) as source:
        if source.width * source.height > 25_000_000:
            raise ValueError('Ảnh quá lớn (tối đa 25 megapixel).')
        image = ImageOps.exif_transpose(source).convert('RGB')
    lut = [max(0, min(255, math.floor((i - 128) * settings['contrast'] +
                                     128 + settings['brightness'] * 255 + 0.5))) for i in range(256)]
    image = image.point(lut * 3)
    if settings.get('crop'):
        x, y, w, h = settings['crop']
        image = image.crop((int(x * image.width), int(y * image.height),
                            max(int(x * image.width) + 1, int((x + w) * image.width)),
                            max(int(y * image.height) + 1, int((y + h) * image.height))))
    return image


def save_version(image, folder, stem, suffix):
    """Exclusive creation prevents overwriting either an original or another edit."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(1, 10000):
        path = folder / f'{stem}_{suffix}_{number:02d}.jpg'
        try:
            stream = path.open('xb')
        except FileExistsError:
            continue
        try:
            with stream:
                image.save(stream, format='JPEG', quality=95, subsampling=0)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path, number
    raise ValueError('Đã đạt giới hạn phiên bản ảnh.')
