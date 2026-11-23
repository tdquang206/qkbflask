"""One process, one reentrant database gate, and recoverable filesystem writes.

The request owns the gate until teardown, including authentication and error
handlers. Storage helpers reenter the same gate; there are no feature locks.
"""
import atexit
import base64
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from functools import wraps

from Crypto.Cipher import AES

DATA_LOCK = threading.RLock()
_local = threading.local()
_instance_handles = {}


def synchronized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with DATA_LOCK:
            return function(*args, **kwargs)
    return wrapped


def atomic_write(path, data):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _cipher_key():
    key = base64.b64decode(os.environ['DB_ENCRYPTION_KEY'], validate=True)
    if len(key) not in (16, 24, 32):
        raise ValueError('DB_ENCRYPTION_KEY must decode to an AES key')
    return key


def seal(data):
    cipher = AES.new(_cipher_key(), AES.MODE_GCM, nonce=os.urandom(16))
    encrypted, tag = cipher.encrypt_and_digest(data)
    return cipher.nonce + tag + encrypted


def unseal(data):
    if len(data) < 32:
        raise ValueError('Encrypted file is incomplete')
    return AES.new(_cipher_key(), AES.MODE_GCM, nonce=data[:16]).decrypt_and_verify(data[32:], data[16:32])


def ensure_single_instance(root):
    """OS-held lock is released on process exit, including a crash."""
    root = Path(root).resolve()
    if root in _instance_handles:
        return
    root.mkdir(parents=True, exist_ok=True)
    stream = open(root / '.qkb-instance.lock', 'a+b')
    stream.seek(0)
    if os.fstat(stream.fileno()).st_size == 0:
        stream.write(b'0')
        stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError('Another QKB instance is using this data directory') from None
    _instance_handles[root] = stream
    atexit.register(stream.close)


class FileTransaction:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / '.qkb-journal' / 'pending'
        self.entries = {}
        self.committed = False

    def _manifest(self, state='pending'):
        atomic_write(self.directory / 'manifest.enc', seal(json.dumps(
            {'state': state, 'entries': self.entries}).encode('utf-8')))

    def capture(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root) or '.qkb-journal' in path.relative_to(self.root).parts:
            raise ValueError('Transaction path is outside the application data directory')
        if path.is_dir():
            raise ValueError('Capture individual files, not directories')
        name = path.relative_to(self.root).as_posix()
        if name in self.entries:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        snapshot = None
        if path.exists():
            snapshot = str(len(self.entries)) + '.enc'
            atomic_write(self.directory / snapshot, seal(path.read_bytes()))
        self.entries[name] = snapshot
        # Persist the before-image before the caller changes the live file.
        self._manifest()

    def finish(self, commit):
        if not self.entries:
            return
        if commit:
            self._manifest('committed')
            self.committed = True
        elif not self.committed:
            self.restore()
        self.cleanup()

    def restore(self):
        for name, snapshot in reversed(list(self.entries.items())):
            path = (self.root / name).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError('Invalid journal path')
            if snapshot is None:
                path.unlink(missing_ok=True)
            else:
                if Path(snapshot).name != snapshot:
                    raise ValueError('Invalid journal snapshot')
                atomic_write(path, unseal((self.directory / snapshot).read_bytes()))

    def cleanup(self):
        if self.directory.resolve() != self.root / '.qkb-journal' / 'pending':
            raise ValueError('Invalid journal directory')
        if self.directory.exists():
            shutil.rmtree(self.directory)


def recover_pending(root):
    with DATA_LOCK:
        transaction = FileTransaction(root)
        manifest = transaction.directory / 'manifest.enc'
        if not manifest.exists():
            # An interrupted first snapshot cannot have changed a live file.
            transaction.cleanup()
            return
        saved = json.loads(unseal(manifest.read_bytes()))
        transaction.entries = saved['entries']
        if saved['state'] == 'pending':
            transaction.restore()
        elif saved['state'] != 'committed':
            raise ValueError('Invalid transaction state; refusing startup')
        transaction.cleanup()


def capture_file(path):
    transaction = getattr(_local, 'transaction', None)
    if transaction is not None:
        transaction.capture(path)


def init_coordination(app):
    from flask import g, request

    @app.before_request
    def acquire_data_gate():
        if request.endpoint == 'static':
            return
        DATA_LOCK.acquire()
        g.data_gate_held = True
        recover_pending(app.config['DATA_ROOT'])
        # GET endpoints must remain read-only. Every state-changing request
        # gets a journal, lazily populated by the first filesystem write.
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            _local.transaction = FileTransaction(app.config['DATA_ROOT'])
        g.data_gate_success = False

    @app.after_request
    def complete_data_operation(response):
        if getattr(g, 'data_gate_held', False):
            body = response.get_json(silent=True) if response.is_json else None
            g.data_gate_success = response.status_code < 400 and not (
                isinstance(body, dict) and (body.get('success') is False or body.get('status') == 'error'))
            transaction = getattr(_local, 'transaction', None)
            if transaction is not None:
                transaction.finish(g.data_gate_success)
                _local.transaction = None
        return response

    @app.teardown_request
    def release_data_gate(error):
        if getattr(g, 'data_gate_held', False):
            try:
                transaction = getattr(_local, 'transaction', None)
                if transaction is not None:
                    transaction.finish(False)
            finally:
                _local.transaction = None
                # Rollback or restore can invalidate TinyDB's query caches.
                import sys
                shared = sys.modules.get('shared_db')
                for database in getattr(shared, 'DATABASES', ()):
                    for table in database.tables():
                        database.table(table).clear_cache()
                        database.table(table)._next_id = None
                g.data_gate_held = False
                DATA_LOCK.release()
