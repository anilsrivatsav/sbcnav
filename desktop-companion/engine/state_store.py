"""Atomic progress checkpoints that tolerate Windows readers and virus scanners."""
import json
import os
import tempfile
import time
from pathlib import Path


def _recovery_path(path):
    return path.with_name(path.stem + '.recovery.json')


def read_state(path):
    """Load the newest valid primary or recovery checkpoint."""
    path = Path(path)
    candidates = []
    for candidate in (path, _recovery_path(path)):
        try:
            candidates.append((candidate.stat().st_mtime_ns, candidate))
        except OSError:
            pass
    for _, candidate in sorted(candidates, reverse=True):
        try:
            value = json.loads(candidate.read_text(encoding='utf-8'))
            if isinstance(value, dict):
                return value
        except (OSError, ValueError):
            pass
    return {}


def _replace(source, target):
    for attempt in range(8):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(.05 * 2 ** attempt, .4))


def write_state(path, value):
    """Persist fully before replacing; return True when recovery storage was used.

    A lock on the primary must not abort invoice collection. A locked directory
    or disk failure still raises if neither checkpoint can be saved. Never
    truncate the last valid primary file as a fallback.
    """
    path = Path(path)
    recovery = _recovery_path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            _replace(temporary, path)
        except PermissionError:
            _replace(temporary, recovery)
            return True
        try:
            recovery.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    finally:
        try:
            Path(temporary).unlink(missing_ok=True)
        except OSError:
            pass
