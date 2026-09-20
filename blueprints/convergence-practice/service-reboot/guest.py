#!/usr/bin/env python3
"""Finite timer action. Dagu owns execution, history, and selected-step retry."""
import hashlib
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

SOURCE = Path('/opt/service-reboot')
WORK = Path('/var/lib/service-reboot')
RUN_ID = 'native-service-reboot-fixture'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix('.pending')
    with temporary.open('x') as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, path)
    directory = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def identity():
    return {
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'machine_id_sha256': digest(Path('/etc/machine-id')),
        'filesystem_uuid': subprocess.check_output(['findmnt', '-n', '-o', 'UUID', '/'], text=True).strip(),
        'disk_token': (SOURCE / 'disk-token').read_text().strip(),
        'run_id': RUN_ID,
    }


def row(stdout):
    value = json.loads(stdout)
    rows = value if isinstance(value, list) else value.get('runs', [])
    matches = [item for item in rows if item.get('dagRunId') == RUN_ID]
    if len(matches) != 1:
        raise ValueError('Expected exactly one native run history row')
    return matches[0]


def run():
    if (WORK / 'after.json').exists():
        return
    spec = importlib.util.spec_from_file_location('frozen_fixture', SOURCE / 'fixture.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    env = {'HOME': '/home/example', 'PATH': '/usr/bin:/bin',
           'DAGU_HOME': str(WORK / 'dagu-home'), 'TMPDIR': str(WORK),
           'XDG_CONFIG_HOME': str(WORK / 'xdg-config'),
           'XDG_CACHE_HOME': str(WORK / 'xdg-cache'), 'DO_NOT_TRACK': '1'}
    base = [str(SOURCE / 'dagu'), '--context', 'local', '--dagu-home', env['DAGU_HOME'],
            '--config', str(WORK / 'config.yaml')]

    def call(label, args, timeout=60):
        # Preserve every native output, including failure, before checking exit.
        metadata = {'argv': args, 'started_utc': datetime.now(timezone.utc).isoformat(), 'timeout_seconds': timeout}
        (WORK / (label + '.command.json')).write_text(json.dumps(metadata, indent=2) + '\n')
        try:
            result = subprocess.run(args, env=env, cwd=WORK, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            (WORK / (label + '.stdout')).write_bytes(error.stdout or b'')
            (WORK / (label + '.stderr')).write_bytes(error.stderr or b'')
            (WORK / (label + '.timeout')).write_text(str(timeout) + '\n')
            metadata.update(ended_utc=datetime.now(timezone.utc).isoformat(), outcome='timeout')
            (WORK / (label + '.command.json')).write_text(json.dumps(metadata, indent=2) + '\n')
            raise
        metadata.update(ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode)
        (WORK / (label + '.command.json')).write_text(json.dumps(metadata, indent=2) + '\n')
        (WORK / (label + '.stdout')).write_bytes(result.stdout)
        (WORK / (label + '.stderr')).write_bytes(result.stderr)
        (WORK / (label + '.exit')).write_text(str(result.returncode) + '\n')
        result.check_returncode()
        return result.stdout.decode()

    current = identity()
    if not (WORK / 'freeze.json').exists():
        (WORK / 'source').mkdir()
        (WORK / 'dagu-home').mkdir()
        for name in ('planner.py', 'test_planner.py'):
            shutil.copyfile(SOURCE / name, WORK / 'source' / name)
        fixture.exclusive(WORK / 'expected.json', fixture.source_hashes(WORK))
        (WORK / 'config.yaml').write_text('check_updates: false\n')
        (WORK / 'reboot.yaml').write_text('\n'.join([
            'type: graph', 'timeout_sec: 90', 'max_active_runs: 1',
            'working_dir: /var/lib/service-reboot', 'steps:',
            '  - id: checkpoint',
            '    run: /usr/bin/python3 -B /opt/service-reboot/fixture.py checkpoint /var/lib/service-reboot',
            '  - id: finalize', '    depends: [checkpoint]',
            '    run: /usr/bin/python3 -B /opt/service-reboot/fixture.py finalize /var/lib/service-reboot', '']))
        version = call('version', [str(SOURCE / 'dagu'), 'version'])
        if '2.16.6' not in version.split():
            raise ValueError('Frozen Dagu version mismatch')
        call('validate', base + ['validate', str(WORK / 'reboot.yaml')])
        freeze = {'source_hashes': {p.name: digest(p) for p in SOURCE.iterdir() if p.is_file()},
                  'workflow_sha256': digest(WORK / 'reboot.yaml'),
                  'config_sha256': digest(WORK / 'config.yaml'),
                  'python_version': platform.python_version(),
                  'python_sha256': digest(Path(sys.executable).resolve()),
                  'kernel_release': platform.release(),
                  'os_release': Path('/etc/os-release').read_text(),
                  'identity': current}
        atomic_json(WORK / 'freeze.json', freeze)
        start_args = base + ['start', '--run-id', RUN_ID, str(WORK / 'reboot.yaml')]
        start_metadata = {'argv': start_args, 'started_utc': datetime.now(timezone.utc).isoformat(),
                          'completion': 'An interrupted parent may have no end metadata; native history is authoritative.'}
        (WORK / 'start.command.json').write_text(json.dumps(start_metadata, indent=2) + '\n')
        with (WORK / 'start.stdout').open('xb') as out, (WORK / 'start.stderr').open('xb') as err:
            child = subprocess.Popen(start_args,
                                     env=env, cwd=WORK, stdout=out, stderr=err)
            deadline = time.monotonic() + 40
            while not (WORK / 'finalize-ready.json').exists():
                if child.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Native finalizer did not reach its wait')
                time.sleep(0.05)
            native = row(call('history-before', base + ['history', '--run-id', RUN_ID, '--format', 'json']))
            if native['status'] != 'running' or (WORK / 'completed.json').exists():
                raise ValueError('Preboot native job must be unfinished and running')
            before = dict(current, native_status=native['status'],
                          checkpoint_sha256=fixture.verify_checkpoint(WORK),
                          claim_sha256=digest(WORK / 'checkpoint-started.json'), effect_count=0)
            atomic_json(WORK / 'before.json', before)
            os.sync()
            # systemd stops the entire owned cgroup during orderly guest reboot.
            # No native stop/retry command is issued by the SSH connection.
            code = child.wait(timeout=100)
            (WORK / 'start.exit').write_text(str(code) + '\n')
            start_metadata.update(ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=code)
            (WORK / 'start.command.json').write_text(json.dumps(start_metadata, indent=2) + '\n')
            raise RuntimeError('Guest was not rebooted while its finalizer waited')
    before = json.loads((WORK / 'before.json').read_text())
    if current['boot_id'] == before['boot_id']:
        raise ValueError('Timer cannot recover on the original boot')
    for key in ('machine_id_sha256', 'filesystem_uuid', 'disk_token', 'run_id'):
        if not before[key] or current[key] != before[key]:
            raise ValueError('Persistent guest identity changed: ' + key)
    freeze = json.loads((WORK / 'freeze.json').read_text())
    if freeze['python_version'] != platform.python_version() or freeze['python_sha256'] != digest(Path(sys.executable).resolve()):
        raise ValueError('Frozen guest Python runtime changed')
    if freeze['source_hashes'] != {p.name: digest(p) for p in SOURCE.iterdir() if p.is_file()}:
        raise ValueError('Frozen guest source changed')
    if digest(WORK / 'reboot.yaml') != freeze['workflow_sha256'] or digest(WORK / 'config.yaml') != freeze['config_sha256']:
        raise ValueError('Frozen native configuration changed')
    if fixture.verify_checkpoint(WORK) != before['checkpoint_sha256']:
        raise ValueError('Checkpoint changed across reboot')
    if (WORK / 'retry-claimed').exists():
        raise ValueError('A prior retry failed; retain it rather than silently retrying')
    (WORK / 'retry-claimed').touch(exist_ok=False)
    interrupted = row(call('history-interrupted', base + ['history', '--run-id', RUN_ID, '--format', 'json']))
    if interrupted['status'] not in ('aborted', 'failed', 'running'):
        raise ValueError('Native history does not show an interrupted run')
    (WORK / 'release-finalize').touch(exist_ok=False)
    call('retry', base + ['retry', '--run-id', RUN_ID, '--step', 'finalize', str(WORK / 'reboot.yaml')], timeout=100)
    native = row(call('history-after', base + ['history', '--run-id', RUN_ID, '--format', 'json']))
    effect = json.loads((WORK / 'completed.json').read_text())
    if native['status'] != 'succeeded' or effect != {'checkpoint_sha256': before['checkpoint_sha256'], 'tests': 12, 'execution_count': 1}:
        raise ValueError('Native completion and one exclusive effect required')
    after = dict(current, native_status=native['status'], interrupted_status=interrupted['status'],
                 checkpoint_sha256=fixture.verify_checkpoint(WORK),
                 claim_sha256=digest(WORK / 'checkpoint-started.json'),
                 effect_count=len(list(WORK.glob('completed.json'))),
                 completed_sha256=digest(WORK / 'completed.json'))
    if after['claim_sha256'] != before['claim_sha256']:
        raise ValueError('Checkpoint execution claim changed')
    atomic_json(WORK / 'after.json', after)


if __name__ == '__main__':
    run()
