"""Verify source workbooks and atomically import their encrypted history snapshot.

Run after Alembic migration 0033. The archive key must be set in the backend
environment and backed up separately from the database.
"""
import argparse
import json
from pathlib import Path

from deskflow_archive import decrypt_archive, encrypt_archive, verify_workbooks


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--history-json', type=Path)
    source.add_argument('--encrypted-input', type=Path)
    parser.add_argument('--workbook-root', type=Path)
    parser.add_argument('--encrypted-output', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.history_json:
        if not args.workbook_root:
            parser.error('--workbook-root is required with --history-json')
        payload = json.loads(args.history_json.read_text())
        manifest = verify_workbooks(payload, args.workbook_root)
        payload['sourceManifest'] = manifest
    else:
        payload = decrypt_archive(args.encrypted_input.read_text())
        manifest = payload['sourceManifest']
    if args.check_only:
        print(json.dumps({'verified': True, 'workbooks': manifest, 'auctionRecords': len(payload['auctionRecords'])}))
        return
    ciphertext = args.encrypted_input.read_text() if args.encrypted_input else encrypt_archive(payload)
    if decrypt_archive(ciphertext)['sourceManifest'] != manifest:
        raise RuntimeError('Encrypted archive round trip failed.')
    if args.encrypted_output:
        args.encrypted_output.write_text(ciphertext)
        print(json.dumps({'encrypted': True, 'workbooks': manifest, 'auctionRecords': len(payload['auctionRecords'])}))
        return
    from sqlalchemy import select
    from database import SessionLocal
    from models import DeskflowWorkbookArchive
    with SessionLocal.begin() as session:
        row = session.execute(select(DeskflowWorkbookArchive).where(DeskflowWorkbookArchive.id == 1).with_for_update()).scalar_one_or_none()
        if row is None:
            session.add(DeskflowWorkbookArchive(id=1, ciphertext=ciphertext))
        else:
            row.ciphertext = ciphertext
    with SessionLocal() as session:
        stored = session.get(DeskflowWorkbookArchive, 1)
        result = decrypt_archive(stored.ciphertext)
        if result['sourceManifest'] != manifest or len(result['auctionRecords']) != len(payload['auctionRecords']):
            raise RuntimeError('Stored archive verification failed.')
    print(json.dumps({'imported': True, 'workbooks': manifest, 'auctionRecords': len(payload['auctionRecords'])}))


if __name__ == '__main__':
    main()
