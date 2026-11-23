"""Offline recovery to a stopped data directory, or verification only."""
import argparse
from pathlib import Path
import sys
import uuid

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))

from dotenv import load_dotenv
load_dotenv(SOURCE_ROOT / '.env')

from utils.coordination import ensure_single_instance, recover_pending
from utils.full_backup import DB_FILES, create_backup, inspect_backup, restore_backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup', type=Path)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--confirm', action='store_true', help='Confirm replacement of the selected data directory')
    args = parser.parse_args()
    manifest = inspect_backup(args.backup.resolve())
    if args.verify_only:
        print(f'Verified {len(manifest["entries"])} recovery entries; no data changed.')
        return
    if not args.confirm:
        parser.error('Restore requires --confirm. Use --verify-only to check the backup first.')
    root = args.data_dir.resolve()
    ensure_single_instance(root)
    recover_pending(root)
    if any((root / name).exists() for name in DB_FILES):
        create_backup(root, root / 'backups' / 'pre_restore')
    restore_backup(root, args.backup.resolve())
    from tinydb import TinyDB
    from utils.storage import EncryptedJSONStorage
    database = TinyDB(root / 'db.json', storage=EncryptedJSONStorage)
    users = database.table('users')
    for user in users.all():
        users.update({'auth_version': uuid.uuid4().hex}, doc_ids=[user.doc_id])
    database.close()
    print('Restore completed and old login sessions revoked. Validate before starting the service.')


if __name__ == '__main__':
    main()
