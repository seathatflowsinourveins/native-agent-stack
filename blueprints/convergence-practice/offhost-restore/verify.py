"""Independent filesystem and encrypted-input checks; no restic or secret access."""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / 'wsl-restore'
_PATH_SAFETY_SPEC = importlib.util.spec_from_file_location(
    "path_safety", HERE.parents[2] / "scripts/path_safety.py")
_path_safety = importlib.util.module_from_spec(_PATH_SAFETY_SPEC)
_PATH_SAFETY_SPEC.loader.exec_module(_path_safety)
OBJECT = re.compile(r'(?:config|data/[0-9a-f]{2}/[0-9a-f]{64}|(?:index|keys|snapshots)/[0-9a-f]{64})\Z')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def repository_manifest(root):
    root = Path(root)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError('repository is not a real directory')
    result = []
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        name = path.relative_to(root).as_posix()
        if not stat.S_ISREG(info.st_mode) or not OBJECT.fullmatch(name):
            raise ValueError('unsupported repository object')
        result.append({'path': name, 'bytes': info.st_size, 'sha256': digest(path)})
    return result


def decode_repository(bundle, expected, target):
    """Decode a text envelope of native ciphertext, never an archive or link."""
    if not isinstance(bundle, dict) or set(bundle) != {'schema_version', 'files'} or bundle['schema_version'] != 1:
        raise ValueError('invalid ciphertext envelope')
    if not isinstance(expected, list) or not expected or len(expected) > 100:
        raise ValueError('invalid ciphertext manifest')
    indexed = {}
    for entry in expected:
        if (set(entry) != {'path', 'bytes', 'sha256'} or not OBJECT.fullmatch(entry['path'])
                or entry['path'] in indexed or type(entry['bytes']) is not int
                or not 0 < entry['bytes'] <= 2_000_000
                or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
            raise ValueError('invalid/duplicate ciphertext object')
        indexed[entry['path']] = entry
    decoded = {}
    for entry in bundle['files']:
        if not isinstance(entry, dict) or set(entry) != {'path', 'base64'}:
            raise ValueError('invalid ciphertext envelope member')
        name = entry['path']
        if name not in indexed or name in decoded:
            raise ValueError('extra or duplicate ciphertext object')
        raw = base64.b64decode(entry['base64'], validate=True)
        if len(raw) != indexed[name]['bytes'] or hashlib.sha256(raw).hexdigest() != indexed[name]['sha256']:
            raise ValueError('ciphertext hash/length mismatch')
        decoded[name] = raw
    if set(decoded) != set(indexed):
        raise ValueError('missing ciphertext object')
    target = Path(target).absolute()
    if '..' in target.parts:
        raise ValueError('repository target traverses a symlink')
    # See scripts/path_safety.py: a symlink is tolerated only when it is a
    # trusted OS-level boundary link (root-owned, not group/world-writable,
    # e.g. macOS's /tmp -> /private/tmp); $TMPDIR grants no exemption.
    _path_safety.refuse_untrusted_symlinks(target, 'repository target traverses a symlink')
    target.mkdir(mode=0o700)  # Existing targets, including symlinks, are refused.
    for name, raw in decoded.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o444)
    (target / 'locks').mkdir()
    if repository_manifest(target) != expected:
        raise ValueError('decoded repository differs from frozen manifest')


def fixture_module():
    spec = importlib.util.spec_from_file_location('offhost_frozen_fixture', BASELINE / 'fixture.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_restore(target, number):
    target = Path(target)
    if not stat.S_ISDIR(target.lstat().st_mode) or {p.name for p in target.iterdir()} != {'fixture'}:
        raise ValueError('restore must contain only the selected fixture')
    frozen = load(BASELINE / f'attempt-2/expected-{number}.json')
    fixture = fixture_module()
    if frozen != fixture.expected_manifest(number):
        raise ValueError('historical independent oracle differs from frozen fixture source')
    actual = fixture.manifest(target / 'fixture')
    if actual != frozen:
        raise ValueError('restored paths/types/bytes/hashes/modes differ')
    return actual


def verify_sources(plan):
    checkout = HERE.parents[2]
    for item in plan['frozen_sources']:
        if digest(checkout / item['path']) != item['sha256']:
            raise ValueError('frozen source changed: ' + item['path'])
