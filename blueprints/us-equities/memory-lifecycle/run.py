#!/usr/bin/env python3
"""Create an empty, network-isolated ai-memory fixture; never import a host store."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
from analyze import summarize

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
    (output / 'home').mkdir()
    (output / 'config.toml').write_text(CONFIG)
    script = Path(__file__).resolve().with_name('exercise.py')
    command = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session',
               '--cap-drop', 'ALL', '--clearenv']
    for source, target in [('/usr', '/usr'), ('/lib', '/lib'), ('/lib64', '/lib64'),
                           ('/etc/ld.so.cache', '/etc/ld.so.cache'),
                           (str(binary), '/ai-memory'), (str(script), '/exercise.py')]:
        command += ['--ro-bind', source, target]
    command += ['--bind', str(output), '/run', '--proc', '/proc', '--dev', '/dev',
                '--tmpfs', '/tmp', '--chdir', '/run', '--setenv', 'HOME', '/run/home',
                '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
                '/usr/bin/python3', '/exercise.py']
    receipt = {'argv': command, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'binary_sha256_before': digest(binary), 'exercise_sha256': digest(script),
               'config_sha256': digest(output / 'config.toml')}
    with (output / 'driver.stdout').open('w') as stdout, (output / 'driver.stderr').open('w') as stderr:
        try:
            receipt['exit_code'] = subprocess.run(command, stdin=subprocess.DEVNULL,
                                                  stdout=stdout, stderr=stderr, timeout=120).returncode
        except subprocess.TimeoutExpired:
            receipt.update(exit_code=None, timeout_seconds=120)
        finally:
            receipt['binary_sha256_after'] = digest(binary)
            receipt['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            (output / 'command.private.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: value for key, value in receipt.items() if key != 'argv'}))
    if receipt['exit_code'] != 0 or receipt['binary_sha256_before'] != receipt['binary_sha256_after']:
        raise SystemExit(1)
    acceptance = summarize(json.loads((output / 'outcomes.json').read_text()))
    (output / 'acceptance.json').write_text(json.dumps(acceptance, indent=2) + '\n')
    print(json.dumps({'acceptance_passed': acceptance['passed'], 'checks': len(acceptance['checks']),
                      'tool_calls': acceptance['tool_calls']}))
    if not acceptance['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
