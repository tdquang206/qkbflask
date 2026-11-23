"""Headless service entry point. HTTPS is terminated by the local reverse proxy."""
import os
from pathlib import Path
from dotenv import load_dotenv

SOURCE_ROOT = Path(__file__).resolve().parent
load_dotenv(SOURCE_ROOT / '.env')
data_root = Path(os.getenv('QKB_DATA_DIR') or SOURCE_ROOT).resolve()
data_root.mkdir(parents=True, exist_ok=True)
os.chdir(data_root)

from app import app
from utils.full_backup import start_backup_scheduler
from waitress import serve

if __name__ == '__main__':
    if app.config['DEBUG']:
        raise RuntimeError('FLASK_DEBUG must be disabled for the LAN service.')
    if not app.config['SESSION_COOKIE_SECURE']:
        raise RuntimeError('Set QKB_LAN_MODE=1 and configure the HTTPS reverse proxy before LAN deployment.')
    from werkzeug.middleware.proxy_fix import ProxyFix
    # Only the local proxy can reach this loopback listener. Trust one hop.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    start_backup_scheduler(app.config['DATA_ROOT'], os.getenv('QKB_BACKUP_DIR'))
    serve(app, host='127.0.0.1', port=int(os.getenv('QKB_PORT', '5000')), threads=4,
          max_request_body_size=24 * 1024 * 1024)
