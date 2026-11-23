from datetime import datetime
import json
import os
import traceback


LOG_FILE = os.path.join(
    os.path.abspath(os.getcwd()),
    'logs',
    'error_log.md'
)


def append_error_log(title, error, context=None):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as handle:
            handle.write('# Error Log\n\n')

    context = {key: value for key, value in (context or {}).items()
               if key in {'route', 'action', 'patient_id', 'exam_id', 'short_exam_id'}}
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Exception messages may embed notes, filenames or secrets. Keep only stack
    # locations; clinical data belongs in encrypted history, not plaintext logs.
    import sys
    exception_type, _, trace = sys.exc_info()
    traceback_text = ''.join(traceback.format_list(traceback.extract_tb(trace))) if trace else ''
    if not traceback_text or traceback_text == 'NoneType: None':
        traceback_text = 'No traceback available'

    lines = [
        f'## {timestamp} - {title}',
        '',
        f'- Error type: {exception_type.__name__ if exception_type else "ApplicationError"}',
    ]

    if context:
        lines.extend([
            '- Context:',
            '```json',
            json.dumps(context, ensure_ascii=False, indent=2, default=str),
            '```',
        ])

    lines.extend([
        '- Traceback:',
        '```text',
        traceback_text,
        '```',
        '',
    ])

    with open(LOG_FILE, 'a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
