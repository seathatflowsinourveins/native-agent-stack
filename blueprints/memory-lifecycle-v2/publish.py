#!/usr/bin/env python3
"""Retain one private run directory (run.py's --out) as sanitized, hash-bound public evidence.

Each retained text file is copied with these declared substitutions, in this order:

1. the private run directory becomes `<run>` and the scratch root `<scratch>`;
2. every UUID-shaped identifier (the disposable store's page ids) becomes `fixture-id-N` and
   every 40-hex Git checkpoint id becomes `fixture-checkpoint-N`, numbered by first
   appearance across the whole run (phase-pre/records.json first), so equal ids stay equal
   and distinct ids stay distinct -- the analyzer's id comparisons give the same verdicts;
3. scripts/host_receipts.py sanitize(): the home directory becomes `~` and the user name
   `<user>`.

server.stderr is retained as its timestamped log records only, with ANSI colour codes
removed (the multi-line migration listing between records is omitted). tools.json and
protocol.jsonl are not copied: the same tools/list response and server output lines are
inside records.json. The disposable store under data/ is not retained; publication.json
records a sha256 over its final file listing instead. publication.json binds every
retained file to the sha256 of its private source, and lists the sources that stay private
with their sha256.

    python3 publish.py --run PRIVATE_RUN_DIR --dest PUBLIC_DIR --scratch SCRATCH_ROOT \
        [--private-map PRIVATE_ALIAS_MAP.json]
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import host_receipts  # noqa: E402  (repository sanitizer: home and user name)

UUID = re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', re.I)
CHECKPOINT = re.compile(r'(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])')
ANSI = re.compile(r'\x1b\[[0-9;]*m')
LOG_RECORD = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
PHASE_FILES = ('records.json', 'outcomes.json', 'timeline.json', 'command.private.json',
               'driver.stdout', 'driver.stderr', 'server-argv.json', 'version.json',
               'namespace.json', 'mountinfo.txt', 'shutdown.json', 'config.toml', 'server.stderr')
TOP_FILES = ('handoff/fixture-state.json', 'acceptance.json', 'run.json')
PRIVATE_ONLY = {'tools.json': 'same tools/list response is retained inside records.json',
                'protocol.jsonl': 'same server output lines are retained as the responses in records.json'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Aliases:
    def __init__(self):
        self.ids, self.checkpoints = {}, {}

    def _sub(self, pattern, table, prefix, text):
        def replace(match):
            key = match.group(0).lower()
            if key not in table:
                table[key] = f'{prefix}-{len(table) + 1}'
            return table[key]
        return pattern.sub(replace, text)

    def apply(self, text):
        text = self._sub(UUID, self.ids, 'fixture-id', text)
        return self._sub(CHECKPOINT, self.checkpoints, 'fixture-checkpoint', text)


def sanitize(text, run_dir, scratch, aliases):
    text = text.replace(str(run_dir), '<run>').replace(str(scratch), '<scratch>')
    return host_receipts.sanitize(aliases.apply(text))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--dest', required=True, type=Path)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--private-map', type=Path)
    args = parser.parse_args()
    run_dir, scratch = args.run.resolve(strict=True), args.scratch.resolve(strict=True)
    if args.dest.exists():
        raise SystemExit('destination must not exist yet')
    sources = [f'phase-{p}/{name}' for p in ('pre', 'post') for name in PHASE_FILES] + list(TOP_FILES)
    aliases, published, private = Aliases(), [], []
    for relative in sources:
        source = run_dir / relative
        if not source.is_file():
            continue
        raw = source.read_bytes()
        text = raw.decode()
        target = relative.replace('command.private.json', 'command.json')
        transform = 'substitutions 1-3'
        if relative.endswith('server.stderr'):
            text = '\n'.join(line for line in ANSI.sub('', text).splitlines() if LOG_RECORD.match(line)) + '\n'
            target += '.records.txt'
            transform = 'ANSI codes removed; timestamped log records only; substitutions 1-3'
        out = sanitize(text, run_dir, scratch, aliases).encode()
        path = args.dest / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(out)
        published.append({'path': target, 'sha256': sha256(out), 'bytes': len(out), 'source': relative,
                          'source_sha256': sha256(raw), 'source_bytes': len(raw), 'transform': transform})
    for phase in ('pre', 'post'):
        for name, reason in PRIVATE_ONLY.items():
            source = run_dir / f'phase-{phase}' / name
            if source.is_file():
                raw = source.read_bytes()
                private.append({'source': f'phase-{phase}/{name}', 'sha256': sha256(raw),
                                'bytes': len(raw), 'reason': reason})
    store = sorted((str(f.relative_to(run_dir / 'data')), sha256(f.read_bytes()))
                   for f in (run_dir / 'data').rglob('*') if f.is_file() and not f.is_symlink())
    manifest = {
        'schema_version': 1,
        'substitutions': [
            'private run directory -> <run>; scratch root -> <scratch>',
            'UUID-shaped ids -> fixture-id-N and 40-hex Git checkpoint ids -> fixture-checkpoint-N, '
            'numbered by first appearance across the run',
            'scripts/host_receipts.py sanitize(): home directory -> ~, user name -> <user>'],
        'not_retained': ['data/ (the disposable ai-memory store)'],
        'store_final_state': {'files': len(store), 'listing_sha256': sha256(json.dumps(store).encode()),
                              'listing': 'sha256 of the JSON list of [relative path, file sha256] pairs'},
        'aliases': {'fixture-id': len(aliases.ids), 'fixture-checkpoint': len(aliases.checkpoints)},
        'published_files': published, 'private_only_files': private,
    }
    (args.dest / 'publication.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if args.private_map:
        args.private_map.write_text(json.dumps({'ids': aliases.ids, 'checkpoints': aliases.checkpoints},
                                               indent=2) + '\n')
    print(json.dumps({'published': len(published), 'private_only': len(private), **manifest['aliases']}))


if __name__ == '__main__':
    main()
