#!/usr/bin/env python3
"""Retain the upstream test runs (run_upstream_tests.py and control.py output) as sanitized
evidence and build the preregistered property map (PREREGISTRATION.md section 7).

Every retained text gets the scratch root replaced by `<scratch>` and scripts/host_receipts.py
sanitize() applied: the home directory becomes `~`, the user name `<user>`, and every
private-content match of scripts/validate.py (a UUID-shaped string, or any other path under
/home or /Users such as the first round's sandbox HOME) becomes `[redacted]`.

- `--out` (the final round): each `<group>/<label>.log` is retained with its receipt. The
  receipt drops its per-test dictionary, which the retained log re-derives
  (`run_upstream_tests.py --reparse` on the private copy); `tests_sha256` binds it. The
  control's mutation diffs and summary are copied too.
- `--superseded-out` (the first round, run while the sandbox HOME still sat under /home,
  which the repository's private-content scanner flags; the final runner uses `/work/home`):
  logs and receipts under `superseded-round-1/`, sanitized the same way. These logs hold
  the source build from each tag checkout, which the final round reused.
- `--extra NAME=PATH` retains one of the other files named in EXTRA, sanitized the same way.
- `--private-only NAME=PATH` lists one of the files named in PRIVATE_ONLY by its sha256
  without publishing it.

property-map.json lists, for each tag's final runs, every test whose name contains one of
the preregistered patterns.

publication.json binds every retained file to the sha256 and size of its private source
(its path relative to the scratch root, written as `<scratch>/...`; a source kept beside
that root, such as a verification output, appears as `<scratch>/../...`), names the transformation
applied, says whether it changed the bytes, and lists the private-only files with their
sha256. The committed scripts in this directory are not retained output and are not listed.

    python3 publish_upstream.py --out ROUND2 --superseded-out ROUND1 --dest DIR --scratch ROOT \
        [--extra NAME=PATH ...] [--private-only NAME=PATH ...]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
import host_receipts  # noqa: E402  (repository sanitizer)

PATTERNS = {
    'ttl_expiry_sweep': ('expir', 'ttl', 'sweep'),
    'scope_isolation': ('scope', 'isolat', 'cross_project', 'workspace', 'global', 'boundar'),
    'persistence_restart': ('restart', 'reopen', 'persist', 'durab', 'surviv', 'shutdown'),
    'supersession_as_of': ('as_of', 'supersed', 'temporal'),
    'delete': ('delete', 'purge', 'tombstone'),
}
EXTRA = {
    'setup.log': 'output of setup.sh: rustup-init, the pinned-tag clones and their commit checks, '
                 'the toolchains and cargo fetch --locked',
    'release-verification.json': 'output of verify_release.py (the 02:58Z rerun)',
    'rustup-init-verification.json': 'output of verify_rustup_init.py',
}
PRIVATE_ONLY = {
    'release-verification-first-run.json':
        'the first verify_release.py run (02:05Z). One field was then renamed because gitleaks flagged the '
        'public digest, and the rerun retained as release-verification.json gave the same digests and verdicts.',
}
SANITIZE = 'scratch root -> <scratch>; scripts/host_receipts.py sanitize()'
RECEIPT = ('per-test dictionary dropped (tests_count and tests_sha256 bind it); log_sha256 and log_bytes '
           'kept as log_sha256_private and log_bytes_private and set to the retained log; ' + SANITIZE)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def status_class(status):
    return 'ignored' if status.startswith('ignored') else {'ok': 'passed', 'FAILED': 'failed'}[status]


def property_map(tests):
    result = {}
    for prop, patterns in PATTERNS.items():
        matched = {key: status for key, status in tests.items()
                   if any(p in key.rsplit(' :: ', 1)[-1].lower() for p in patterns)}
        counts = {'matched': len(matched), 'passed': 0, 'failed': 0, 'ignored': 0}
        for status in matched.values():
            counts[status_class(status)] += 1
        result[prop] = {'patterns': list(patterns), 'counts': counts, 'tests': matched}
    return result


def clean(text, scratch):
    return host_receipts.sanitize(text.replace(scratch, '<scratch>'))


def trimmed(receipt, log_bytes_published=None, log_sha256_published=None):
    tests = receipt.pop('tests')
    receipt['log_sha256_private'] = receipt.pop('log_sha256')
    receipt['log_bytes_private'] = receipt.pop('log_bytes')
    if log_sha256_published:
        receipt['log_sha256'], receipt['log_bytes'] = log_sha256_published, log_bytes_published
        receipt['log_sanitization'] = SANITIZE
    receipt['tests_count'] = len(tests)
    receipt['tests_sha256'] = sha256(json.dumps(tests, sort_keys=True, separators=(',', ':')).encode())
    return receipt, tests


class Publication:
    """Writes retained files under dest and records each one against its private source."""

    def __init__(self, dest, scratch):
        self.dest, self.scratch, self.files, self.private = dest, scratch, [], []

    def source(self, path):
        return '<scratch>/' + Path(os.path.relpath(Path(path).resolve(), self.scratch)).as_posix()

    def write(self, relative, data, source, transform):
        target = self.dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry = {'path': relative, 'sha256': sha256(data), 'bytes': len(data)}
        if source is None:
            entry.update(source=None, transform=transform)
        else:
            raw = Path(source).read_bytes()
            entry.update(source=self.source(source), source_sha256=sha256(raw), source_bytes=len(raw),
                         transform=transform, changed_by_transform=raw != data)
        self.files.append(entry)

    def copy(self, relative, source):
        self.write(relative, clean(Path(source).read_text(errors='replace'), self.scratch).encode(), source, SANITIZE)

    def private_only(self, name, source):
        raw = Path(source).read_bytes()
        self.private.append({'name': name, 'source': self.source(source), 'sha256': sha256(raw),
                             'bytes': len(raw), 'reason': PRIVATE_ONLY[name]})

    def manifest(self):
        return {
            'schema_version': 1,
            'substitutions': ['private upstream scratch root -> <scratch>',
                              'scripts/host_receipts.py sanitize(): home directory -> ~, user name -> <user>, '
                              'private-content matches of scripts/validate.py -> [redacted]'],
            'not_retained': ['the tag checkouts, Rust toolchain, cargo registry, sandbox HOME and /tmp '
                             'directories, and cargo target directories under the scratch root',
                             'the rustup-init binary (its sha256 is in rustup-init-verification.json)'],
            'extra_files': {name: EXTRA[name] for name in sorted(EXTRA) if any(f['path'] == name for f in self.files)},
            'published_files': sorted(self.files, key=lambda entry: entry['path']),
            'private_only_files': sorted(self.private, key=lambda entry: entry['name']),
        }


def named(values, allowed, flag):
    pairs = []
    for value in values:
        name, separator, path = value.partition('=')
        if not separator or name not in allowed:
            raise SystemExit(f'{flag} takes NAME=PATH with NAME one of {sorted(allowed)}')
        pairs.append((name, Path(path)))
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--superseded-out', type=Path)
    parser.add_argument('--dest', required=True, type=Path)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--extra', action='append', default=[], metavar='NAME=PATH')
    parser.add_argument('--private-only', action='append', default=[], metavar='NAME=PATH')
    args = parser.parse_args()
    extras = named(args.extra, EXTRA, '--extra')
    private_only = named(args.private_only, PRIVATE_ONLY, '--private-only')
    scratch = str(args.scratch.resolve())
    publication = Publication(args.dest, scratch)
    maps = {}
    for receipt_path in sorted(args.out.glob('*/*.receipt.json')):
        group, label = receipt_path.parent.name, receipt_path.name.removesuffix('.receipt.json')
        receipt = json.loads(receipt_path.read_text())
        log_path = receipt_path.parent / receipt['log']
        raw_log = log_path.read_bytes()
        if sha256(raw_log) != receipt['log_sha256']:
            raise SystemExit(f'{receipt_path}: log does not match its receipt')
        log = clean(raw_log.decode(errors='replace'), scratch).encode()
        publication.write(f'{group}/{receipt["log"]}', log, log_path, SANITIZE)
        receipt, tests = trimmed(receipt, len(log), sha256(log))
        publication.write(f'{group}/{receipt_path.name}', (clean(json.dumps(receipt, indent=2), scratch) + '\n').encode(),
                          receipt_path, RECEIPT)
        if group.startswith('v'):
            maps[f'{group}/{label}'] = {'tag': receipt['tag'], 'commit': receipt['commit'],
                                        'upstream_command': receipt['upstream_command'],
                                        'exit_code': receipt['exit_code'], 'totals': receipt['totals'],
                                        'properties': property_map(tests)}
    for extra in sorted(args.out.glob('control/*.diff')) + sorted(args.out.glob('control/control-summary.json')):
        publication.copy(f'control/{extra.name}', extra)
    if args.superseded_out:
        for receipt_path in sorted(args.superseded_out.glob('*/*.receipt.json')):
            receipt = json.loads(receipt_path.read_text())
            log_path = receipt_path.parent / receipt['log']
            raw_log = log_path.read_bytes()
            if sha256(raw_log) != receipt['log_sha256']:
                raise SystemExit(f'{receipt_path}: log does not match its receipt')
            log = clean(raw_log.decode(errors='replace'), scratch).encode()
            group = f'superseded-round-1/{receipt_path.parent.name}'
            publication.write(f'{group}/{receipt["log"]}', log, log_path, SANITIZE)
            receipt, _tests = trimmed(receipt, len(log), sha256(log))
            receipt['superseded'] = ('first round, result as recorded here; its sandbox HOME sat under /home, '
                                     'which the repository private-content scanner flags, so every command was '
                                     'rerun in the final round with HOME=/work/home')
            publication.write(f'{group}/{receipt_path.name}',
                              (clean(json.dumps(receipt, indent=2), scratch) + '\n').encode(),
                              receipt_path, RECEIPT + '; superseded note added')
    out = {'schema_version': 1, 'method': 'name-based relevance (PREREGISTRATION.md section 7); '
           'a match is not a claim that the upstream test equals a fixture check',
           'runs': maps}
    publication.write('property-map.json', (clean(json.dumps(out, indent=2), scratch) + '\n').encode(), None,
                      'built by this script from the per-test results of the final-round v*/ receipts '
                      '(bound by their tests_sha256)')
    for name, path in extras:
        publication.copy(name, path)
    for name, path in private_only:
        publication.private_only(name, path)
    (args.dest / 'publication.json').write_text(clean(json.dumps(publication.manifest(), indent=2), scratch) + '\n')
    print(json.dumps({key: {prop: value['counts'] for prop, value in run['properties'].items()}
                      for key, run in maps.items()}, indent=1))


if __name__ == '__main__':
    main()
