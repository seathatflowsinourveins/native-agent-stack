#!/usr/bin/env python3
"""Discriminating control for the upstream TTL test (PREREGISTRATION.md section 7).

Runs `ttl_expiry_lifecycle_end_to_end` of `ai-memory-consolidate` at the v2.4.1 checkout
through run_upstream_tests.py four times:

  0. unmodified                         -> expected pass
  1. `not_expired()` returns an empty fragment, as preregistered
     (`let _ = (table, now_param);` keeps `-D warnings` from failing the build)
                                          -> expected fail
  2. `not_expired()` keeps its placeholder but always matches (`OR 1 = 1`), which
     disarms only the expiry condition   -> expected fail at the "expired hidden" assertion
  3. file restored byte-for-byte         -> expected pass

Mutation 2 was added after the freeze: the fragment's placeholders (`?3`, `?`, ...) are
bound positionally, so the preregistered empty fragment can fail on a parameter-count
error instead of on the expiry semantics. Both are run and reported. Each mutation's diff
is retained, and the original file's sha256 is checked after the restore.

A run counts as passed when the runner exits 0 and its receipt shows the selected test
passed, and as failed when the runner exits nonzero and its receipt shows a failed test.
A build error, an empty selection or a missing receipt is neither. The control refuses to
start when any of its output files exists. Once the four runs are done it writes
control-summary.json, whether or not they were as expected, and exits 1 unless they gave
pass, fail, fail, pass and the file was restored byte-for-byte. An error that stops the
control earlier exits nonzero with a traceback and no summary; the mutation loop's finally
block restores the file first.

    python3 control.py --scratch SCRATCH --out DIR
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

RUNNER = Path(__file__).resolve().with_name('run_upstream_tests.py')
TARGET = 'crates/ai-memory-store/src/reader.rs'
ORIGINAL = '''fn not_expired(table: &str, now_param: &str) -> String {
    format!(" AND ({table}.expires_at IS NULL OR {table}.expires_at > {now_param})")
}'''
MUTATIONS = {
    'control-1-empty-fragment': '''fn not_expired(table: &str, now_param: &str) -> String {
    let _ = (table, now_param);
    String::new()
}''',
    'control-2-filter-always-true': '''fn not_expired(table: &str, now_param: &str) -> String {
    format!(" AND ({table}.expires_at IS NULL OR {table}.expires_at > {now_param} OR 1 = 1)")
}''',
}
EXPECTED = {'control-0-unmodified': 'passed', 'control-1-empty-fragment': 'failed',
            'control-2-filter-always-true': 'failed', 'control-3-restored': 'passed'}


def run(scratch, out, label):
    command = [sys.executable, str(RUNNER), '--scratch', str(scratch), '--tag', 'v2.4.1', '--out', str(out),
               '--package', 'ai-memory-consolidate', '--filter', 'ttl_expiry_lifecycle_end_to_end',
               '--label', label]
    return subprocess.run(command, capture_output=True, text=True).returncode


def verdict(out, label, exit_code):
    """'passed' or 'failed' as defined above, from the runner's exit status and its receipt."""
    receipt = out / f'{label}.receipt.json'
    if not receipt.is_file():
        return 'neither: no receipt'
    totals = json.loads(receipt.read_text())['totals']
    if exit_code == 0 and totals['failed'] == 0 and totals['passed'] > 0:
        return 'passed'
    if exit_code != 0 and totals['failed'] > 0:
        return 'failed'
    return f'neither: runner exit {exit_code}, {totals["passed"]} passed, {totals["failed"]} failed'


def problems(summary):
    """Every way the control's result differs from pass, fail, fail, pass with the file restored."""
    found = [f'{label}: expected {expected}, observed {summary["verdicts"].get(label, "no run")}'
             for label, expected in EXPECTED.items() if summary['verdicts'].get(label) != expected]
    if not summary['restored_sha256_matches']:
        found.append(f'{TARGET} was not restored byte-for-byte')
    return found


def write_new(path, text):
    with path.open('x') as stream:  # exclusive: never replaces an earlier control's output
        stream.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    outputs = ([args.out / f'{label}{suffix}' for label in EXPECTED for suffix in ('.log', '.receipt.json')]
               + [args.out / f'{label}.diff' for label in MUTATIONS] + [args.out / 'control-summary.json'])
    existing = [str(path) for path in outputs if os.path.lexists(path)]
    if existing:
        raise SystemExit(f'{", ".join(existing)} already exists: an earlier control is kept as it is. '
                         'Give this control its own --out.')
    args.out.mkdir(parents=True, exist_ok=True)
    source = args.scratch / 'tags' / 'v2.4.1' / TARGET
    original = source.read_bytes()
    original_sha256 = hashlib.sha256(original).hexdigest()
    if original.decode().count(ORIGINAL) != 1:
        raise SystemExit('not_expired() does not have the reviewed shape')
    summary = {'target': TARGET, 'original_sha256': original_sha256, 'runs': {}}
    summary['runs']['control-0-unmodified'] = run(args.scratch, args.out, 'control-0-unmodified')
    try:
        for label, replacement in MUTATIONS.items():
            mutated = original.decode().replace(ORIGINAL, replacement)
            source.write_text(mutated)
            write_new(args.out / f'{label}.diff', ''.join(difflib.unified_diff(
                original.decode().splitlines(keepends=True), mutated.splitlines(keepends=True),
                f'a/{TARGET}', f'b/{TARGET}')))
            summary['runs'][label] = run(args.scratch, args.out, label)
            source.write_bytes(original)
    finally:
        source.write_bytes(original)
    summary['restored_sha256_matches'] = hashlib.sha256(source.read_bytes()).hexdigest() == original_sha256
    summary['runs']['control-3-restored'] = run(args.scratch, args.out, 'control-3-restored')
    summary['expected'] = EXPECTED
    summary['verdicts'] = {label: verdict(args.out, label, code) for label, code in summary['runs'].items()}
    summary['problems'] = problems(summary)
    summary['as_expected'] = not summary['problems']
    write_new(args.out / 'control-summary.json', json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))
    if summary['problems']:
        print('control not as expected: ' + '; '.join(summary['problems']), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
