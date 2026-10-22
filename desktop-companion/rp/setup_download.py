"""Serve a private, preconfigured setup only to the authorised dashboard origin."""
from pathlib import Path
import json

FILENAME = 'SBC-NAV-Office-Setup-2.2.0.exe'


def installer_path(state):
    folder = Path(state) / 'Windows setup'
    path = folder / FILENAME
    manifest = folder / 'installer.json'
    if not (Path(state) / 'operator.key').is_file() or not path.is_file() or not manifest.is_file():
        return None
    try:
        value = json.loads(manifest.read_text(encoding='utf-8-sig'))
        if value.get('filename') != FILENAME or value.get('size') != path.stat().st_size:
            return None
        with path.open('rb') as stream:
            if stream.read(2) != b'MZ':
                return None
    except (OSError, ValueError):
        return None
    return path
