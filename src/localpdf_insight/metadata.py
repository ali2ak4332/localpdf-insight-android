"""Explicit UTF-8 metadata IO; never guess a legacy encoding or reset a library."""
import hashlib
import json
import os
import re
from pathlib import Path


def read_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError('Expected an object')
        return value
    except (UnicodeError, ValueError) as exc:
        recovery = path.with_name(path.name + '.recovery-' + hashlib.sha256(raw).hexdigest()[:16])
        if not recovery.exists():
            recovery.write_bytes(raw)
        raise ValueError('Library metadata is not valid UTF-8 JSON. Original bytes were preserved. '
                         'Restore a known-good backup or explicitly convert a verified legacy encoding; '
                         'do not delete the library file.') from exc


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def convert_legacy(path, encoding):
    """Offline, explicit conversion only. Verify the source encoding yourself."""
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw.decode(encoding, errors='strict'))
    if not isinstance(value, dict):
        raise ValueError('Expected library object; original left unchanged')
    backup = path.with_name(path.name + '.before-conversion-' + hashlib.sha256(raw).hexdigest()[:16])
    if not backup.exists():
        backup.write_bytes(raw)
    write_json(path, value)
    return backup


def managed_pdf(root, document_id):
    if not isinstance(document_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', document_id):
        raise ValueError('Invalid managed document identity')
    directory = (Path(root) / 'documents').resolve()
    path = (directory / (document_id + '.pdf')).resolve()
    if not path.is_relative_to(directory):
        raise ValueError('Managed PDF points outside the document directory')
    return path


def rebase_verified(root, library):
    """Relocation is permitted only for the same content-addressed PDF revision."""
    from .evidence import digest
    changed = False
    for key, item in library.items():
        if item.get('id') != key:
            raise ValueError('Library identity mismatch; original metadata retained')
        path = managed_pdf(root, key)
        if str(path) == item.get('path'):
            continue
        if path.is_file() and digest(path) == item.get('revision'):
            stat = path.stat()
            item.update(path=str(path), size=stat.st_size, mtime_ns=stat.st_mtime_ns)
            changed = True
    if changed:
        metadata = Path(root) / 'library.json'
        raw = metadata.read_bytes()
        backup = metadata.with_name(metadata.name + '.before-rebase-' + hashlib.sha256(raw).hexdigest()[:16])
        if not backup.exists():
            backup.write_bytes(raw)
        write_json(metadata, library)
    return changed
