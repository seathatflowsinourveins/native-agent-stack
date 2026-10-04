#!/usr/bin/env python3
"""Run ai-memory's own CI test command, unchanged, at a pinned release tag.

This script only launches and records the upstream command. The tests, their
selection and pass/fail verdicts are upstream's: `cargo test --workspace
--all-targets` is the `test` job of the tag's own `.github/workflows/ci.yml`
(v2.4.1's workflow adds `cargo test --workspace --doc`). The toolchain comes
from the tag's `rust-toolchain.toml` through official rustup.

The command runs inside bubblewrap with every namespace unshared (no network,
loopback only), a HOME and /tmp created fresh for each run, and only the checkout, the
scratch Rust toolchain/registry and the read-only system runtime mounted. No
real home directory, memory store or service socket is visible, so a test
cannot reach a production ai-memory store or port.

    python3 run_upstream_tests.py --scratch DIR --tag v2.4.1 --out DIR \
        [--filter NAME] [--no-fail-fast] [--doc] [--label LABEL]
    python3 run_upstream_tests.py --reparse RECEIPT

Writes <out>/<label>.log (stdout and stderr combined in emission order) and
<out>/<label>.receipt.json (argv, environment, the toolchain versions reported inside
the sandbox, this script's own sha256, times, exit code, log sha256, parsed per-test
results). It refuses to start when either file already exists and creates both
exclusively, so an earlier attempt's log and receipt are never truncated or replaced: a
rerun, such as the `--no-fail-fast` follow-up to a failed run, needs its own --label or
--out. `--reparse` prints a receipt with its parsed fields recomputed from its retained
log and leaves the receipt file as it is. Standard library only.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

TEST_LINE = re.compile(r'^test (\S+) \.\.\. (ok|FAILED|ignored(?:, .*)?)$')
# A test that spawns a process can have that process's output land between the name and
# its status; the status then arrives alone on a later line.
TEST_START = re.compile(r'^test (\S+) \.\.\. ')
STATUS_ONLY = re.compile(r'^(ok|FAILED|ignored(?:, .*)?)$')
RESULT_LINE = re.compile(r'^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored; '
                         r'(\d+) measured; (\d+) filtered out')
RUNNING_LINE = re.compile(r'^\s+(Running|Doc-tests) (.+)$')
ENV = {
    # The ci.yml `env` block sets RUSTFLAGS and CARGO_TERM_COLOR=always; colour is
    # turned off here only so the retained log is plain text.
    'RUSTFLAGS': '-D warnings', 'CARGO_TERM_COLOR': 'never',
    'CARGO_NET_OFFLINE': 'true', 'CARGO_INCREMENTAL': '0',
    'HOME': '/work/home', 'USER': 'runner', 'LANG': 'C.UTF-8', 'TZ': 'UTC',
    'RUSTUP_HOME': '/work/rust/rustup', 'CARGO_HOME': '/work/rust/cargo',
    'PATH': '/work/rust/cargo/bin:/usr/local/bin:/usr/bin:/bin',
}


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse(log_text):
    tests, binaries, current, pending = {}, [], None, None
    for line in log_text.splitlines():
        running = RUNNING_LINE.match(line)
        if running:
            current = running.group(2).strip()
            continue
        match = TEST_LINE.match(line)
        if match or (pending and STATUS_ONLY.match(line)):
            name, status = (match.group(1), match.group(2)) if match else (pending, line)
            key = f'{current} :: {name}' if current else name
            tests[key] = status
            pending = None
            continue
        started = TEST_START.match(line)
        if started:
            pending = started.group(1)
            continue
        result = RESULT_LINE.match(line)
        if result:
            binaries.append({'binary': current, 'result': result.group(1),
                             'passed': int(result.group(2)), 'failed': int(result.group(3)),
                             'ignored': int(result.group(4)), 'filtered_out': int(result.group(6))})
    totals = {k: sum(b[k] for b in binaries) for k in ('passed', 'failed', 'ignored')}
    totals['test_binaries'] = len(binaries)
    return tests, binaries, totals


def bwrap(scratch, tag, run_id, inner):
    checkout = scratch / 'tags' / tag
    home = scratch / 'sandbox' / tag / run_id / 'home'
    tmp = scratch / 'sandbox' / tag / run_id / 'tmp'
    home.mkdir(parents=True)
    tmp.mkdir(parents=True)
    command = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session',
               '--cap-drop', 'ALL', '--clearenv',
               '--ro-bind', '/usr', '/usr', '--ro-bind', '/etc', '/etc',
               '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/sbin', '/sbin',
               '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
               '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/run', '--tmpfs', '/var/tmp',
               '--bind', str(tmp), '/tmp', '--bind', str(home), '/work/home',
               '--bind', str(scratch / 'rust'), '/work/rust',
               '--bind', str(checkout), '/work/ai-memory', '--chdir', '/work/ai-memory']
    for key, value in ENV.items():
        command += ['--setenv', key, value]
    return command + inner


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--scratch', type=Path)
    parser.add_argument('--tag')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--label', default='workspace-all-targets')
    parser.add_argument('--doc', action='store_true', help='cargo test --workspace --doc')
    parser.add_argument('--no-fail-fast', action='store_true')
    parser.add_argument('--package')
    parser.add_argument('--filter')
    parser.add_argument('--timeout', type=int, default=5400)
    parser.add_argument('--reparse', type=Path,
                        help='print an existing receipt with its parsed fields recomputed from its retained log '
                             '(the receipt file is not changed)')
    args = parser.parse_args()
    if args.reparse:
        receipt = json.loads(args.reparse.read_text())
        log = args.reparse.with_name(receipt['log'])
        if digest(log) != receipt['log_sha256']:
            raise SystemExit('retained log does not match the receipt hash')
        tests, binaries, totals = parse(log.read_text(errors='replace'))
        receipt.update(totals=totals, test_binaries=binaries,
                       failed_tests=sorted(k for k, v in tests.items() if v == 'FAILED'),
                       tests=dict(sorted(tests.items())))
        print(json.dumps(receipt, indent=2))
        return
    if not (args.scratch and args.tag and args.out):
        parser.error('--scratch, --tag and --out are required unless --reparse is given')
    log = args.out / f'{args.label}.log'
    receipt_path = args.out / f'{args.label}.receipt.json'
    existing = [str(path) for path in (log, receipt_path) if os.path.lexists(path)]
    if existing:
        raise SystemExit(f'{" and ".join(existing)} already exists: an earlier attempt is kept as it is. '
                         'Give this run its own --label or --out.')
    cargo_args = ['--workspace', '--doc'] if args.doc else ['--workspace', '--all-targets']
    if args.package:
        cargo_args = ['-p', args.package, '--all-targets']
    if args.no_fail_fast:
        cargo_args.append('--no-fail-fast')
    if args.filter:
        cargo_args.append(args.filter)
    args.out.mkdir(parents=True, exist_ok=True)
    checkout = args.scratch / 'tags' / args.tag
    head = subprocess.run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], capture_output=True,
                          text=True, check=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(checkout), 'status', '--porcelain', '--untracked-files=no'],
                           capture_output=True, text=True, check=True).stdout.strip()
    run_id = f"{args.label}-{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%S%fZ}"
    toolchain = subprocess.run(bwrap(args.scratch, args.tag, run_id + '-toolchain',
                                     ['sh', '-c', 'rustc --version; cargo --version']),
                               stdin=subprocess.DEVNULL, capture_output=True, text=True)
    command = bwrap(args.scratch, args.tag, run_id, ['cargo', 'test'] + cargo_args)
    started = datetime.datetime.now(datetime.timezone.utc)
    with log.open('x') as stream:  # exclusive: never truncates an existing log
        try:
            exit_code = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stream,
                                       stderr=subprocess.STDOUT, timeout=args.timeout).returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            exit_code, timed_out = None, True
    finished = datetime.datetime.now(datetime.timezone.utc)
    tests, binaries, totals = parse(log.read_text(errors='replace'))
    receipt = {
        'tag': args.tag, 'commit': head, 'tracked_files_modified': bool(dirty),
        'upstream_command': ['cargo', 'test'] + cargo_args,
        'runner_sha256': digest(__file__),
        'toolchain_in_sandbox': toolchain.stdout.strip().splitlines(),
        'working_directory': '/work/ai-memory (the tag checkout, inside the sandbox)',
        'environment': ENV,
        'sandbox_argv': [a.replace(str(args.scratch), '<scratch>') for a in command],
        'started_utc': started.isoformat(), 'finished_utc': finished.isoformat(),
        'duration_seconds': round((finished - started).total_seconds(), 1),
        'exit_code': exit_code, 'timed_out': timed_out,
        'log': log.name, 'log_sha256': digest(log), 'log_bytes': log.stat().st_size,
        'totals': totals, 'test_binaries': binaries,
        'failed_tests': sorted(k for k, v in tests.items() if v == 'FAILED'),
        'tests': dict(sorted(tests.items())),
    }
    with receipt_path.open('x') as stream:  # exclusive: never replaces an existing receipt
        stream.write(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('tag', 'upstream_command', 'exit_code', 'duration_seconds',
                                                'totals', 'failed_tests')}))
    raise SystemExit(0 if exit_code == 0 else 1)


if __name__ == '__main__':
    main()
