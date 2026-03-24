from datetime import datetime
import json
import os
import traceback


LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'logs',
    'error_log.md'
)


def append_error_log(title, error, context=None):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8') as handle:
            handle.write('# Error Log\n\n')

    context = context or {}
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    traceback_text = traceback.format_exc().strip()
    if not traceback_text or traceback_text == 'NoneType: None':
        traceback_text = 'No traceback available'

    lines = [
        f'## {timestamp} - {title}',
        '',
        f'- Error: {error}',
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
