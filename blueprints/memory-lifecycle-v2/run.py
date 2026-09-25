#!/usr/bin/env python3
"""Create TWO disposable, network-isolated ai-memory fixtures against the SAME store: a
"pre" native stdio server process that runs the v2 lifecycle fixture
(blueprints/memory-lifecycle-v2/PREREGISTRATION.md), then, only after that process has
fully exited, a "post" native stdio server process -- a genuinely separate OS process, in
its own bubblewrap sandbox -- pointed at the same --data-dir, to check restart durability.

Standard library only, and the bubblewrap recipe/CLI shape is v1's
(blueprints/us-equities/memory-lifecycle/run.py), reused by attribution: never import a
host store, never touch a real home/account/memory directory, reject a non-fresh output
directory, reject an output path under the binary's own install directory.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402  (local, stdlib-only; see analyze.py)

CONFIG = '''embedding_provider = "none"
backfill_on_start = false
run_autowire = false
capture_assistant = false
consolidate_on_session_end = false
[maintenance]
enabled = false
[auto_improve]
require_approval = true
on_session_end = false
[auto_improve.scheduler]
enabled = false
interval_secs = 0
'''


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bwrap_command(binary, script, phase_dir):
    command = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session',
               '--cap-drop', 'ALL', '--clearenv']
    for source, target in [('/usr', '/usr'), ('/lib', '/lib'), ('/lib64', '/lib64'),
                           ('/etc/ld.so.cache', '/etc/ld.so.cache'),
                           (str(binary), '/ai-memory'), (str(script), '/exercise.py')]:
        command += ['--ro-bind', source, target]
    command += ['--bind', str(phase_dir), '/run']
    return command


def run_phase(phase, binary, exercise_script, output, shared_data, shared_handoff):
    phase_dir = output / f'phase-{phase}'
    phase_dir.mkdir(mode=0o700)
    (phase_dir / 'home').mkdir()
    (phase_dir / 'config.toml').write_text(CONFIG)
    command = bwrap_command(binary, exercise_script, phase_dir)
    # Nested binds for the two things this phase SHARES with the other phase: the actual
    # ai-memory store, and this harness's own (non-ai-memory) handoff file. Everything else
    # under /run is private to this phase's own directory.
    command += ['--bind', str(shared_data), '/run/data']
    command += ['--bind', str(shared_handoff), '/run/handoff']
    command += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', '/run',
                '--setenv', 'HOME', '/run/home', '--setenv', 'PATH', '/usr/bin:/bin',
                '--setenv', 'LANG', 'C.UTF-8',
                '/usr/bin/python3', '/exercise.py', '--phase', phase]
    receipt = {'argv': command, 'phase': phase,
               'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'binary_sha256_before': digest(binary)}
    with (phase_dir / 'driver.stdout').open('w') as stdout, \
         (phase_dir / 'driver.stderr').open('w') as stderr:
        try:
            receipt['exit_code'] = subprocess.run(command, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, timeout=180).returncode
        except subprocess.TimeoutExpired:
            receipt.update(exit_code=None, timeout_seconds=180)
        finally:
            receipt['binary_sha256_after'] = digest(binary)
            receipt['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (phase_dir / 'command.private.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'argv'}))
    if receipt['exit_code'] != 0 or receipt['binary_sha256_before'] != receipt['binary_sha256_after']:
        raise SystemExit(f'phase {phase} failed or binary changed on disk -- see {phase_dir}')
    return phase_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    binary, output = args.binary.resolve(strict=True), args.out.resolve()
    if not binary.is_file() or output.is_relative_to(binary.parent):
        raise ValueError('select an executable file and an output outside its installation')
    if output.exists():
        raise ValueError('output must be a NEW directory, containing no existing data')
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    shared_data = output / 'data'
    shared_handoff = output / 'handoff'
    shared_data.mkdir(mode=0o700)
    shared_handoff.mkdir(mode=0o700)
    exercise_script = Path(__file__).resolve().with_name('exercise.py')

    pre_dir = run_phase('pre', binary, exercise_script, output, shared_data, shared_handoff)
    # The bwrap invocation above has returned: that process tree, including the native
    # server it launched, has fully exited before this line runs (subprocess.run blocks).
    post_dir = run_phase('post', binary, exercise_script, output, shared_data, shared_handoff)

    outcomes_pre = json.loads((pre_dir / 'outcomes.json').read_text())
    outcomes_post = json.loads((post_dir / 'outcomes.json').read_text())
    handoff = json.loads((shared_handoff / 'fixture-state.json').read_text())
    pre_result = analyze.summarize_pre(outcomes_pre)
    post_result = analyze.summarize_post(outcomes_post, handoff)
    acceptance = {'passed': pre_result['passed'] and post_result['passed'],
                  'binary_sha256': digest(binary),
                  'pre': pre_result, 'post': post_result}
    (output / 'acceptance.json').write_text(json.dumps(acceptance, indent=2) + '\n')
    print(json.dumps({'acceptance_passed': acceptance['passed'],
                      'pre_checks': len(pre_result['checks']), 'pre_tool_calls': pre_result['tool_calls'],
                      'post_checks': len(post_result['checks']), 'post_tool_calls': post_result['tool_calls']}))
    if not acceptance['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
