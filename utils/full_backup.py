"""Coordinated recovery sets; each opaque ZIP member is AES-GCM encrypted.

No plaintext archive is written to disk. The encryption key is deliberately
excluded and must be kept in separate recovery custody.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import threading
import time
import uuid
import zipfile
import tempfile
import re
from datetime import datetime, timezone, timedelta

from utils.coordination import DATA_LOCK, FileTransaction, atomic_write, capture_file, seal, unseal

DB_FILES = ('db.json', 'db_services.json', 'money_log.json', 'db_mua_thuoc.json')
CONFIG_FILES = ('user_settings.json', 'exam_template.json')
TREES = ('uploads', 'files', 'logs')


def _safe_target(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
        raise ValueError('Invalid backup member path')
    if name not in DB_FILES + CONFIG_FILES and (not relative.parts or relative.parts[0] not in TREES):
        raise ValueError('Backup member is not application data')
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Backup path escapes data directory')
    return target


def inspect_backup(path):
    """Authenticate every entry and validate all DBs before any restore write."""
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(unseal(archive.read('manifest.enc')))
        if manifest.get('format') != 1:
            raise ValueError('Unsupported recovery-set format')
        entries = manifest['entries']
        names = [entry['path'] for entry in entries]
        if len(names) != len(set(names)) or set(DB_FILES) - set(names):
            raise ValueError('Incomplete or duplicate database manifest')
        for entry in entries:
            _safe_target(Path.cwd().resolve(), entry['path'])
            if entry['member'] is None:
                if entry['path'] not in DB_FILES + CONFIG_FILES:
                    raise ValueError('Only uninitialized database/config files may be absent')
                continue
            content = unseal(_encrypted_member(path, archive, manifest, entry['member']))
            if hashlib.sha256(content).hexdigest() != entry['sha256']:
                raise ValueError('Recovery-set checksum mismatch')
            if entry['path'] in DB_FILES:
                if not isinstance(json.loads(unseal(content)), dict):
                    raise ValueError('Invalid TinyDB snapshot')
        return manifest


def _encrypted_member(path, archive, manifest, member):
    if manifest.get('external_blobs'):
        if not re.fullmatch(r'[a-f0-9]{64}\.enc', member):
            raise ValueError('Invalid encrypted blob identifier')
        directory = Path(path).resolve().parent
        target = (directory / 'blobs' / member).resolve()
        if not target.is_relative_to(directory):
            raise ValueError('Encrypted blob escapes the backup destination')
        return target.read_bytes()
    return archive.read(member)


def create_backup(root, destination=None, incremental=False):
    root = Path(root).resolve()
    destination = Path(destination or root / 'backups' / 'full').resolve()
    if any(destination.is_relative_to(root / tree) for tree in TREES + ('.qkb-journal',)):
        raise ValueError('Backup destination cannot be inside live media, logs or the recovery journal')
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    final = destination / f'qkb_{stamp}_{uuid.uuid4().hex[:8]}.qkb'
    temporary = final.with_suffix('.partial')
    with DATA_LOCK:
        entries = []
        paths = [root / name for name in DB_FILES + CONFIG_FILES]
        for tree in TREES:
            folder = root / tree
            if folder.exists():
                paths.extend(sorted(path for path in folder.rglob('*') if path.is_file()))
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
                for path in paths:
                    if path.is_symlink() or not path.resolve().is_relative_to(root):
                        raise ValueError('Symlinked/external data cannot be backed up')
                    name = path.relative_to(root).as_posix()
                    entry = {'path': name, 'member': None}
                    if path.exists():
                        content = path.read_bytes()
                        digest = hashlib.sha256(content).hexdigest()
                        entry.update(member=f'{digest}.enc' if incremental else f'{len(entries)}.enc', sha256=digest)
                        if incremental:
                            blob = destination / 'blobs' / entry['member']
                            if not blob.resolve().is_relative_to(destination):
                                raise ValueError('Encrypted blob escapes the backup destination')
                            if not blob.exists():
                                atomic_write(blob, seal(content))
                        else:
                            archive.writestr(entry['member'], seal(content))
                    entries.append(entry)
                manifest = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                            'entries': entries, 'external_blobs': incremental,
                            'application': 'QKBFlask LAN file trial'}
                archive.writestr('manifest.enc', seal(json.dumps(manifest).encode('utf-8')))
            with open(temporary, 'r+b') as stream:
                os.fsync(stream.fileno())
            inspect_backup(temporary)
            os.replace(temporary, final)
        finally:
            temporary.unlink(missing_ok=True)
    return final


def restore_backup(root, path):
    root = Path(root).resolve()
    with DATA_LOCK:
        manifest = inspect_backup(path)
        # Reuse an enclosing request journal; otherwise own a recovery journal.
        from utils import coordination
        own = getattr(coordination._local, 'transaction', None) is None
        transaction = FileTransaction(root) if own else coordination._local.transaction
        try:
            with zipfile.ZipFile(path) as archive:
                for entry in manifest['entries']:
                    target = _safe_target(root, entry['path'])
                    transaction.capture(target)
                    if entry['member'] is None:
                        target.unlink(missing_ok=True)
                    else:
                        atomic_write(target, unseal(_encrypted_member(path, archive, manifest, entry['member'])))
            if own:
                transaction.finish(True)
        except Exception:
            if own:
                transaction.finish(False)
            raise
        return manifest


def portable_backup(path):
    """Return a self-contained encrypted ZIP stream, including shared blobs."""
    manifest = inspect_backup(path)
    stream = tempfile.TemporaryFile('w+b')
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as target:
            for index, entry in enumerate(manifest['entries']):
                if entry['member'] is not None:
                    encrypted = _encrypted_member(path, source, manifest, entry['member'])
                    entry['member'] = f'{index}.enc'
                    target.writestr(entry['member'], encrypted)
            manifest['external_blobs'] = False
            target.writestr('manifest.enc', seal(json.dumps(manifest).encode('utf-8')))
        stream.seek(0)
        return stream
    except Exception:
        stream.close()
        raise


def retain_backups(destination, now=None):
    """Keep 48h of points, 30 daily and 12 monthly; collect unused blobs."""
    destination = Path(destination).resolve()
    now = now or datetime.now(timezone.utc)
    with DATA_LOCK:
        records = []
        for path in destination.glob('qkb_*.qkb'):
            if path.is_symlink() or path.parent.resolve() != destination:
                raise ValueError('Invalid backup retention target')
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(unseal(archive.read('manifest.enc')))
            created = datetime.fromisoformat(manifest['created_at'])
            records.append((created, path, manifest))
        records.sort(key=lambda value: value[0], reverse=True)
        keep, days, months = set(), set(), set()
        for created, path, _ in records:
            clinic = created.astimezone(timezone(timedelta(hours=7)))
            day, month = clinic.strftime('%Y-%m-%d'), clinic.strftime('%Y-%m')
            if (now - created).total_seconds() <= 48 * 3600:
                keep.add(path)
            if day not in days and len(days) < 30:
                keep.add(path)
                days.add(day)
            if month not in months and len(months) < 12:
                keep.add(path)
                months.add(month)
        referenced = set()
        for _, path, manifest in records:
            if path in keep and manifest.get('external_blobs'):
                referenced.update(e['member'] for e in manifest['entries'] if e['member'])
        for _, path, _ in records:
            if path not in keep:
                path.unlink()
        for blob in (destination / 'blobs').glob('*.enc'):
            if blob.name not in referenced and not blob.is_symlink() and blob.parent.resolve() == destination / 'blobs':
                blob.unlink()


def start_backup_scheduler(root, destination=None, interval=900):
    """Runs between coordinated requests, so snapshots contain committed data."""
    root = Path(root).resolve()

    def run():
        while True:
            started = time.monotonic()
            status_path = root / 'backups' / 'status.json'
            try:
                status = json.loads(status_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                status = {}
            try:
                today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7))).date().isoformat()
                create_backup(root, destination, incremental=status.get('last_full_day') == today)
                retain_backups(destination or root / 'backups' / 'full')
                status = {'last_success': datetime.now(timezone.utc).isoformat(), 'last_full_day': today, 'error': None}
            except Exception:
                # Do not include paths, keys or raw exception text in the status UI.
                status.update(last_attempt=datetime.now(timezone.utc).isoformat(),
                              error='Backup failed; inspect disk space, destination access and encryption key.')
            try:
                atomic_write(status_path, json.dumps(status).encode('utf-8'))
            except OSError:
                import logging
                logging.getLogger(__name__).error('Cannot write backup status; inspect disk space and permissions.')
            time.sleep(max(1, interval - (time.monotonic() - started)))

    thread = threading.Thread(target=run, daemon=True, name='qkb-full-backup')
    thread.start()
    return thread
