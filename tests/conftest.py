"""Never import the production app against the clinic's live data directory."""
import atexit
import base64
import os
from pathlib import Path
import tempfile

SOURCE_ROOT = Path(__file__).resolve().parents[1]
original_directory = Path.cwd()
test_directory = SOURCE_ROOT / '.test-tmp-lan-suite'
test_directory.mkdir(exist_ok=True)
session_directory = Path(tempfile.mkdtemp(prefix='session-', dir=test_directory))
os.environ['DB_ENCRYPTION_KEY'] = base64.b64encode(b'SyntheticTestKeyOnly-32Bytes!!!!!'[:32].ljust(32, b'!')).decode('ascii')
os.environ['SECRET_KEY'] = 'synthetic-test-session-secret'
os.environ['QKB_BOOTSTRAP_PASSWORD'] = 'synthetic-bootstrap-password'
os.chdir(session_directory)
atexit.register(os.chdir, original_directory)
