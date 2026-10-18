"""Encryption and source reconciliation for the Deskflow workbook archive."""
from __future__ import annotations

import hashlib
import json
import os
import zlib
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from openpyxl import load_workbook


def _fernet() -> Fernet:
    key = os.getenv('DESKFLOW_ARCHIVE_KEY', '')
    if not key:
        raise RuntimeError('DESKFLOW_ARCHIVE_KEY is required to read workbook history.')
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise RuntimeError('DESKFLOW_ARCHIVE_KEY is invalid.') from exc


def encrypt_archive(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return _fernet().encrypt(zlib.compress(raw, level=9)).decode()


@lru_cache(maxsize=2)
def decrypt_archive(ciphertext: str) -> dict:
    try:
        return json.loads(zlib.decompress(_fernet().decrypt(ciphertext.encode())))
    except (InvalidToken, ValueError, zlib.error) as exc:
        raise RuntimeError('Workbook archive could not be decrypted. Check DESKFLOW_ARCHIVE_KEY.') from exc


def _serialise(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, float, bool)):
        return value
    return str(value)


def verify_workbooks(payload: dict, root: Path) -> dict:
    """Compare every populated source cell, formula and hidden-row flag to the extract."""
    expected = {book['id']: book for book in payload['workbooks']}
    if set(expected) != {'parcels', 'catering', 'others'}:
        raise ValueError('Expected the three known Deskflow workbooks.')
    manifest = {}
    total_rows = total_cells = 0
    for book in payload['workbooks']:
        source = (root / book['sourceRelativePath']).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file():
            raise ValueError(f"Missing source workbook: {book['sourceRelativePath']}")
        formula_book = load_workbook(source, data_only=False, read_only=False)
        value_book = load_workbook(source, data_only=True, read_only=False)
        try:
            if [s.title for s in formula_book.worksheets] != [s['name'] for s in book['sheets']]:
                raise ValueError(f'Sheet list differs: {source.name}')
            rows_in_book = cells_in_book = 0
            for extracted_sheet in book['sheets']:
                sheet = formula_book[extracted_sheet['name']]
                values_sheet = value_book[sheet.title]
                populated = sorted({cell.row for cell in sheet._cells.values() if cell.value is not None})
                extracted_rows = extracted_sheet['rows']
                if populated != [row['n'] for row in extracted_rows]:
                    raise ValueError(f'Row list differs: {source.name} / {sheet.title}')
                for row in extracted_rows:
                    n = row['n']
                    if bool(sheet.row_dimensions[n].hidden) != row['hidden']:
                        raise ValueError(f'Hidden row differs: {source.name} / {sheet.title} / {n}')
                    actual_values = []
                    actual_formulas = {}
                    for column in range(1, sheet.max_column + 1):
                        cell = sheet._cells.get((n, column))
                        raw = cell.value if cell else None
                        cached = values_sheet._cells.get((n, column))
                        if isinstance(raw, str) and raw.startswith('='):
                            actual_formulas[str(column)] = raw
                            actual_values.append(_serialise(cached.value if cached else None))
                        else:
                            actual_values.append(_serialise(raw))
                        if raw is not None:
                            cells_in_book += 1
                    while actual_values and actual_values[-1] is None:
                        actual_values.pop()
                    if actual_values != row['v'] or actual_formulas != row['f']:
                        raise ValueError(f'Cell differs: {source.name} / {sheet.title} / {n}')
                rows_in_book += len(populated)
            if rows_in_book != book['rowCount'] or cells_in_book != book['cellCount']:
                raise ValueError(f'Count differs: {source.name}')
            total_rows += rows_in_book
            total_cells += cells_in_book
            manifest[book['id']] = {
                'file': book['file'], 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'sheets': len(book['sheets']), 'rows': rows_in_book, 'cells': cells_in_book,
            }
        finally:
            formula_book.close()
            value_book.close()
    if (total_rows, total_cells, len(payload['auctionRecords'])) != (
        payload['totalRows'], payload['totalCells'], payload['auctionRecordCount']
    ):
        raise ValueError('Extract totals differ from workbook totals.')
    return manifest
