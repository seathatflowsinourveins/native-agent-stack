#!/usr/bin/env python3
"""Run only on an explicitly owned disposable Ubuntu runner; never reboots it."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tarfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_PATH_SAFETY_SPEC = importlib.util.spec_from_file_location("path_safety", ROOT / "scripts/path_safety.py")
_path_safety = importlib.util.module_from_spec(_PATH_SAFETY_SPEC)
_PATH_SAFETY_SPEC.loader.exec_module(_path_safety)
MARKER = 'NATIVE_REBOOT_OBSERVER '
GUEST_ARCHIVE = ('sudo /usr/bin/tar --exclude=./dagu-home/data/auth '
                 '-C /var/lib/service-reboot -czf - .')


def qemu_arguments(disk, private, serial, port):
    # QEMU8.2.2's virtio-blk device owns `serial`; the qcow2 backend does not.
    # Keep a separately named backend, matching upstream virtio-blk qtests.
    return ['qemu-system-x86_64', '-machine', 'accel=tcg', '-m', '2048', '-smp', '2',
            '-display', 'none', '-monitor', 'none',
            # ttyS0 remains the boot console. Its getty may hang up open clients;
            # the observer writes to the separate ttyS1 channel instead.
            '-serial', 'file:' + str(serial.with_name('boot-serial.log')),
            '-serial', 'file:' + str(serial),
            '-drive', 'file=' + str(disk) + ',format=qcow2,if=none,id=service-reboot-disk',
            '-device', 'virtio-blk-pci,drive=service-reboot-disk,serial=native-reboot-disk',
            '-drive', 'file=' + str(private / 'seed.iso') + ',format=raw,media=cdrom,readonly=on',
            '-drive', 'file=' + str(private / 'payload.iso') + ',format=raw,media=cdrom,readonly=on',
            '-netdev', f'user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:{port}-:22',
            '-device', 'virtio-net-pci,netdev=net0', '-no-shutdown']


def verify_block_device_help(output):
    for name in ('drive', 'serial'):
        if not re.search(r'^\s*' + name + r'=<str>(?:\s|$)', output, re.MULTILINE):
            raise ValueError('Native virtio-blk-pci lacks required device property: ' + name)


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def process_identity(pid):
    # /proc stat starttime disambiguates PID reuse. Parse after the final ')'
    # because process names can contain spaces and parentheses.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return [pid, fields[19]]


def observer_records(serial):
    records = []
    for line in serial.splitlines():
        if MARKER in line:
            try:
                records.append(json.loads(line.split(MARKER, 1)[1]))
            except json.JSONDecodeError:
                continue  # The serial writer may still be completing its line.
    return records


def check_evidence(before, after, observations, host):
    if before['boot_id'] == after['boot_id']:
        raise ValueError('Kernel boot ID did not change')
    for key in ('machine_id_sha256', 'filesystem_uuid', 'disk_token', 'run_id',
                'checkpoint_sha256', 'claim_sha256'):
        if not before[key] or before[key] != after[key]:
            raise ValueError('Persistent identity or checkpoint changed: ' + key)
    if before['native_status'] != 'running' or before['effect_count'] != 0:
        raise ValueError('Preboot job was not unfinished and running')
    if after['native_status'] != 'succeeded' or after['effect_count'] != 1:
        raise ValueError('Postboot native success and one effect required')
    for phase, record in (('before', before), ('after', after)):
        matches = [r for r in observations if r['phase'] == phase and r['boot_id'] == record['boot_id']]
        if len(matches) != 1 or matches[0]['linger'] is not True or matches[0]['user_manager'] != 'active':
            raise ValueError('Automatic lingering user-manager observation missing')
    if host['disk_before'] != host['disk_after'] or host['qemu_before'] != host['qemu_after']:
        raise ValueError('VM process or persistent disk was replaced')
    events = host['events']
    if not (events['before_observed'] < events['reboot_requested'] <
            events['after_observed'] < events['postboot_ssh_started']):
        raise ValueError('Postboot SSH preceded automatic serial completion')


def audit_guest(guest, observations, host, frozen):
    before = json.loads((guest / 'before.json').read_text())
    after = json.loads((guest / 'after.json').read_text())
    check_evidence(before, after, observations, host)
    for phase in ('before', 'after'):
        observation = next(r for r in observations if r['phase'] == phase)
        if observation['record_sha256'] != digest(guest / (phase + '.json')):
            raise ValueError('Serial observation differs from retained record')
        value = json.loads((guest / ('history-' + phase + '.stdout')).read_text())
        rows = value if isinstance(value, list) else value.get('runs', [])
        matches = [r for r in rows if r.get('dagRunId') == before['run_id']]
        if len(matches) != 1 or matches[0]['status'] != (before if phase == 'before' else after)['native_status']:
            raise ValueError('Native history differs from declared state')
    sources = {name: digest(guest / 'source' / name) for name in ('planner.py', 'test_planner.py')}
    if sources != {name: frozen['payload_hashes'][name] for name in sources}:
        raise ValueError('Accepted source or oracle changed')
    checkpoint = json.loads((guest / 'checkpoint.json').read_text())
    if checkpoint != {'execution_count': 1, 'tests': 12, 'sources': sources}:
        raise ValueError('Checkpoint execution count or oracle differs')
    if json.loads((guest / 'checkpoint-started.json').read_text()) != {'execution_count': 1}:
        raise ValueError('Checkpoint was reexecuted')
    if digest(guest / 'checkpoint.json') != before['checkpoint_sha256'] or digest(guest / 'checkpoint-started.json') != before['claim_sha256']:
        raise ValueError('Retained checkpoint differs from preboot bytes')
    effect = json.loads((guest / 'completed.json').read_text())
    if effect != {'checkpoint_sha256': before['checkpoint_sha256'], 'tests': 12, 'execution_count': 1}:
        raise ValueError('Final effect violates the frozen contract')
    if digest(guest / 'completed.json') != after['completed_sha256']:
        raise ValueError('Final effect changed after observation')
    guest_freeze = json.loads((guest / 'freeze.json').read_text())
    if guest_freeze['source_hashes'] != frozen['payload_hashes']:
        raise ValueError('Guest payload does not match the preboot host freeze')
    if guest_freeze['workflow_sha256'] != digest(guest / 'reboot.yaml') or guest_freeze['config_sha256'] != digest(guest / 'config.yaml'):
        raise ValueError('Frozen native configuration changed')
    for label in ('checkpoint-tests', 'final-tests'):
        log = (guest / (label + '.log')).read_text()
        if 'Ran 12 tests' not in log or not log.rstrip().endswith('OK'):
            raise ValueError('Original 12-test oracle did not pass')
    if (guest / 'retry.exit').read_text().strip() != '0':
        raise ValueError('Native retry failed')
    return {'status': 'passed', 'scope': 'one orderly owned Ubuntu guest kernel reboot',
            'same_native_run_id': True, 'checkpoint_execution_count': 1,
            'checkpoint_tests': 12, 'final_tests': 12, 'local_effect_count': 1,
            'automatic_completion_before_postboot_ssh': True, 'model_calls': 0,
            'provider_usage': 'not_applicable', 'token_savings_claim': False}


def run(work):
    if not work.is_absolute() or work.exists() or work.is_symlink():
        raise ValueError('--work must be a new absolute path without symlink ancestors')
    # See scripts/path_safety.py: a symlink is tolerated only when it is a
    # trusted OS-level boundary link (root-owned, not group/world-writable,
    # e.g. macOS's /tmp -> /private/tmp); $TMPDIR grants no exemption.
    _path_safety.refuse_untrusted_symlinks(work, '--work must be a new absolute path without symlink ancestors')
    # Execution is intentionally unavailable on an existing desktop host.
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('Execution requires the declared disposable GitHub-hosted runner')
    os.umask(0o077)
    work.mkdir(mode=0o700)
    reports, private, payload = [work / p for p in ('reports', 'private', 'payload')]
    for path in (reports, private, payload):
        path.mkdir()
    plan = json.loads((HERE / 'plan.json').read_text())
    deadline = time.monotonic() + plan['deadline_seconds']
    env = {'HOME': str(private), 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'}
    qemu = None
    ssh = None
    result = None
    events = {}

    def command(label, args, timeout=120, data=None, check=True):
        available = max(1, min(timeout, deadline - time.monotonic()))
        metadata = {'argv': args, 'started_utc': datetime.now(timezone.utc).isoformat(), 'timeout_seconds': available}
        write_json(reports / (label + '.command.json'), metadata)
        try:
            result = subprocess.run(args, input=data, capture_output=True, env=env, timeout=available)
        except subprocess.TimeoutExpired as error:
            (reports / (label + '.stdout')).write_bytes(error.stdout or b'')
            (reports / (label + '.stderr')).write_bytes(error.stderr or b'')
            (reports / (label + '.timeout')).write_text(str(available) + '\n')
            metadata.update(ended_utc=datetime.now(timezone.utc).isoformat(), outcome='timeout')
            write_json(reports / (label + '.command.json'), metadata)
            raise
        metadata.update(ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode)
        write_json(reports / (label + '.command.json'), metadata)
        (reports / (label + '.stdout')).write_bytes(result.stdout)
        (reports / (label + '.stderr')).write_bytes(result.stderr)
        (reports / (label + '.exit')).write_text(str(result.returncode) + '\n')
        if check:
            result.check_returncode()
        return result

    def download(url, path, expected=None):
        # No authentication headers, checkout environment, or runner tokens.
        with urllib.request.urlopen(url, timeout=60) as response, path.open('xb') as out:
            while chunk := response.read(1024 * 1024):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Download exceeded experiment deadline')
                out.write(chunk)
        if expected and digest(path) != expected:
            raise ValueError('Pinned download checksum mismatch: ' + path.name)

    try:
        image_path = private / 'noble-server-cloudimg-amd64.img'
        download(plan['ubuntu']['url'], image_path, plan['ubuntu']['sha256'])
        base = plan['ubuntu']['url'].rsplit('/', 1)[0]
        for name in ('SHA256SUMS', 'SHA256SUMS.gpg'):
            download(base + '/' + name, reports / name)
        signature = command('ubuntu-signature', [
            'gpgv', '--status-fd', '1', '--keyring', '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg',
            str(reports / 'SHA256SUMS.gpg'), str(reports / 'SHA256SUMS')])
        if ('[GNUPG:] VALIDSIG ' + plan['ubuntu']['signer_fingerprint']) not in signature.stdout.decode():
            raise ValueError('Official cloud-image signing fingerprint mismatch')
        signed = [line.split()[0] for line in (reports / 'SHA256SUMS').read_text().splitlines()
                  if line.split()[-1].lstrip('*') == image_path.name]
        if signed != [plan['ubuntu']['sha256']]:
            raise ValueError('Signed image checksum differs from the frozen plan')
        archive = private / 'dagu.tar.gz'
        download(plan['dagu']['url'], archive, plan['dagu']['archive_sha256'])
        with tarfile.open(archive) as bundle:
            member = bundle.getmember('dagu')
            if not member.isfile():
                raise ValueError('Dagu archive member is not a regular file')
            (payload / 'dagu').write_bytes(bundle.extractfile(member).read())
        if digest(payload / 'dagu') != plan['dagu']['binary_sha256']:
            raise ValueError('Native binary checksum mismatch')
        source_paths = list(HERE.glob('*.py')) + list(HERE.glob('*.service')) + list(HERE.glob('*.timer')) + [HERE / 'setup.sh', HERE / 'plan.json']
        source_paths += [ROOT / 'blueprints/convergence-practice/job-recovery/fixture.py',
                         ROOT / 'blueprints/convergence-practice/native-worker/accepted/planner.py',
                         ROOT / 'blueprints/convergence-practice/native-worker/seed/test_planner.py']
        # The guest receives only explicitly selected public sources and binary.
        for source in source_paths:
            shutil.copyfile(source, payload / source.name)
        (payload / 'disk-token').write_text(os.urandom(32).hex() + '\n')
        key = private / 'ssh-key'
        command('keygen', ['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)])
        cloud = {'users': [{'name': 'example', 'uid': 1001, 'lock_passwd': True,
                             'shell': '/bin/bash', 'sudo': ['ALL=(root) NOPASSWD: /usr/bin/systemctl reboot, /usr/bin/tar, /usr/bin/journalctl'],
                             'ssh_authorized_keys': [(key.with_suffix('.pub')).read_text().strip()]}],
                 'ssh_pwauth': False, 'disable_root': True,
                 'package_update': False, 'package_upgrade': False,
                 'write_files': [{'path': '/root/setup-reboot.sh', 'permissions': '0700',
                                  'content': (HERE / 'setup.sh').read_text()}],
                 'runcmd': [['/bin/sh', '/root/setup-reboot.sh']]}
        (private / 'user-data').write_text('#cloud-config\n' + json.dumps(cloud))
        (private / 'meta-data').write_text('instance-id: native-service-reboot\nlocal-hostname: owned-reboot\n')
        command('cloud-seed', ['cloud-localds', str(private / 'seed.iso'), str(private / 'user-data'), str(private / 'meta-data')])
        command('payload-iso', ['genisoimage', '-quiet', '-output', str(private / 'payload.iso'), '-volid', 'REBOOT_INPUT', '-joliet', '-rock', str(payload)])
        disk = private / 'persistent.qcow2'
        command('disk-create', ['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(image_path), str(disk), '8G'])
        command('qemu-version', ['qemu-system-x86_64', '--version'])
        device_help = command('qemu-block-device-help', ['qemu-system-x86_64', '-device', 'virtio-blk-pci,help'])
        verify_block_device_help((device_help.stdout + device_help.stderr).decode())
        command('runner-packages', ['dpkg-query', '-W', 'qemu-system-x86', 'qemu-utils', 'cloud-image-utils', 'ubuntu-cloudimage-keyring'])
        # scripts/path_safety.py is a host-side-only dependency of run()'s own
        # symlink-ancestor check, never shipped to the guest -- tracked here
        # (not in source_paths, which is copied into payload/) so a changed
        # helper still shows up in repository_inputs.
        inputs = sorted(set(source_paths + [p for p in HERE.iterdir() if p.is_file()] +
                            [ROOT / '.github/workflows/native-service-reboot.yml', ROOT / 'tests/test_service_reboot.py',
                             ROOT / 'scripts/path_safety.py']))
        frozen = {'repository_inputs': {str(p.relative_to(ROOT)): digest(p) for p in inputs},
                  'payload_hashes': {p.name: digest(p) for p in payload.iterdir()},
                  'image_sha256': digest(image_path), 'dagu_archive_sha256': digest(archive),
                  'seed_sha256': digest(private / 'seed.iso'), 'payload_iso_sha256': digest(private / 'payload.iso'),
                  'qemu_binary_sha256': digest(Path(shutil.which('qemu-system-x86_64'))),
                  'ubuntu_keyring_sha256': digest(Path('/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg')),
                  'frozen_monotonic': time.monotonic()}
        write_json(reports / 'freeze.json', frozen)
        with socket.socket() as candidate:
            candidate.bind(('127.0.0.1', 0))
            port = candidate.getsockname()[1]
        ssh = ['ssh', '-i', str(key), '-p', str(port), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
               '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + str(private / 'known_hosts'),
               '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ConnectTimeout=10', 'example@127.0.0.1']
        serial = reports / 'serial.log'
        args = qemu_arguments(disk, private, serial, port)
        write_json(reports / 'qemu.command.json', {'argv': args, 'started_utc': datetime.now(timezone.utc).isoformat()})
        with (reports / 'qemu.stdout').open('xb') as out, (reports / 'qemu.stderr').open('xb') as err:
            qemu = subprocess.Popen(args, env=env, stdout=out, stderr=err, start_new_session=True)
        disk_before = [disk.stat().st_dev, disk.stat().st_ino]
        qemu_before = process_identity(qemu.pid)

        def wait_observation(phase):
            while time.monotonic() < deadline:
                if qemu.poll() is not None:
                    raise RuntimeError('Owned QEMU exited before observation')
                records = observer_records(serial.read_text(errors='replace') if serial.exists() else '')
                found = [r for r in records if r['phase'] == phase]
                if found:
                    if len(found) != 1:
                        raise ValueError('Duplicate observer phase')
                    events[phase + '_observed'] = time.monotonic()
                    return found[0]
                time.sleep(0.25)
            raise TimeoutError('Automatic serial observation deadline exceeded')

        wait_observation('before')
        events['reboot_requested'] = time.monotonic()
        reboot = command('guest-reboot', ssh + ['sudo /usr/bin/systemctl reboot'], check=False, timeout=30)
        if reboot.returncode not in (0, 255):
            raise ValueError('Guest reboot request failed')
        # Deliberately no SSH reachability probes, logins, retries or commands here.
        wait_observation('after')
        events['postboot_ssh_started'] = time.monotonic()
        collected = command('guest-archive', ssh + [GUEST_ARCHIVE], timeout=90)
        (reports / 'guest.tar.gz').write_bytes(collected.stdout)
        (reports / 'guest-archive.stdout').unlink()  # Binary retained under its named archive.
        command('guest-journal', ssh + ['sudo /usr/bin/journalctl --no-pager -o short-monotonic'], timeout=60)
        command('guest-boots', ssh + ['sudo /usr/bin/journalctl --no-pager --list-boots'], timeout=30)
        guest = reports / 'guest'
        guest.mkdir()
        with tarfile.open(fileobj=io.BytesIO(collected.stdout), mode='r:gz') as bundle:
            # Python 3.12's data filter rejects links escaping the extraction root.
            bundle.extractall(guest, filter='data')
        observations = observer_records(serial.read_text(errors='replace'))
        host = {'disk_before': disk_before, 'disk_after': [disk.stat().st_dev, disk.stat().st_ino],
                'qemu_before': qemu_before, 'qemu_after': process_identity(qemu.pid) if qemu.poll() is None else None,
                'events': events}
        write_json(reports / 'host-observations.json', host)
        for path, expected in frozen['repository_inputs'].items():
            if digest(ROOT / path) != expected:
                raise ValueError('Frozen repository input changed during trial')
        result = audit_guest(guest, observations, host, frozen)
        return result
    except BaseException as error:
        write_json(reports / 'failure.json', {'status': 'failed', 'error_type': type(error).__name__,
                                            'detail': str(error), 'events': events})
        # Failure is final before diagnostic access can activate a user manager.
        # These commands only collect evidence and can never produce acceptance.
        if qemu is not None and qemu.poll() is None and ssh is not None:
            for label, remote in (
                ('failed-guest-archive', GUEST_ARCHIVE),
                ('failed-guest-journal', 'sudo /usr/bin/journalctl --no-pager -o short-monotonic'),
            ):
                metadata = {'argv': ssh + [remote], 'started_utc': datetime.now(timezone.utc).isoformat(),
                            'timeout_seconds': 30, 'diagnostic_after_terminal_failure': True}
                write_json(reports / (label + '.command.json'), metadata)
                try:
                    diagnostic = subprocess.run(ssh + [remote], env=env, capture_output=True, timeout=30)
                    (reports / (label + '.stdout')).write_bytes(diagnostic.stdout)
                    (reports / (label + '.stderr')).write_bytes(diagnostic.stderr)
                    (reports / (label + '.exit')).write_text(str(diagnostic.returncode) + '\n')
                    metadata.update(exit_code=diagnostic.returncode)
                except subprocess.TimeoutExpired as timed_out:
                    (reports / (label + '.stdout')).write_bytes(timed_out.stdout or b'')
                    (reports / (label + '.stderr')).write_bytes(timed_out.stderr or b'')
                    (reports / (label + '.timeout')).write_text('30\n')
                    metadata.update(outcome='timeout')
                metadata.update(ended_utc=datetime.now(timezone.utc).isoformat())
                write_json(reports / (label + '.command.json'), metadata)
        raise
    finally:
        cleanup_errors = []
        try:
            if qemu is not None and qemu.poll() is None:
                try:
                    os.killpg(qemu.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # The still-owned process exited between poll and signal.
                try:
                    qemu.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(qemu.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    qemu.wait(timeout=10)
        except Exception as error:
            cleanup_errors.append(type(error).__name__ + ': ' + str(error))
        finally:
            # Filesystem cleanup is independent of process teardown races.
            for directory in (private, payload):
                try:
                    shutil.rmtree(directory)
                except Exception as error:
                    cleanup_errors.append(type(error).__name__ + ': ' + str(error))
        if qemu is not None:
            try:
                metadata = json.loads((reports / 'qemu.command.json').read_text())
                metadata.update(ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=qemu.poll())
                write_json(reports / 'qemu.command.json', metadata)
            except Exception as error:
                cleanup_errors.append(type(error).__name__ + ': ' + str(error))
        write_json(reports / 'cleanup.json', {'owned_qemu_retired': qemu is None or qemu.poll() is not None,
                                              'private_key_removed': not private.exists(),
                                              'owned_disks_removed': not private.exists(),
                                              'errors': cleanup_errors})
        if cleanup_errors:
            raise RuntimeError('Owned cleanup failed; see retained cleanup.json')
        if result is not None and not (reports / 'failure.json').exists():
            write_json(reports / 'result.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.work), indent=2))
