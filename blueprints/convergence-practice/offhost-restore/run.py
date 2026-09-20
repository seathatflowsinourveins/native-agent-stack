"""Restore fixed synthetic ciphertext in credential-free, network-isolated native processes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
from verify import HERE, decode_repository, digest, load, repository_manifest, verify_restore, verify_sources


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    path.chmod(0o644)


def sanitize(text):
    return re.sub(r'by \S+@synthetic-wsl-restore', 'by $SOURCE_USER@synthetic-wsl-restore', text)


def sandbox_command(binary, repository, key, output, probe, native):
    # sudo is provided by the workflow for this entire recorder. The native process
    # receives only these mounts and environment entries; it has no host network.
    return ['/usr/bin/bwrap', '--unshare-all', '--unshare-net', '--die-with-parent', '--new-session',
            '--clearenv', '--uid', '1000', '--gid', '1000', '--cap-drop', 'ALL',
            '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
            '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
            '--ro-bind', str(binary), '/tool/restic',
            '--ro-bind', str(probe), '/input/probe.py',
            '--ro-bind', str(repository), '/repository', '--ro-bind', str(key), '/secret/password',
            '--bind', str(output), '/out', '--chdir', '/out',
            '--setenv', 'HOME', '/tmp', '--setenv', 'PATH', '/usr/bin:/bin',
            '--setenv', 'PWD', '/out',
            '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1',
            '/usr/bin/python3', '-I', '/input/probe.py',
            '--no-cache', '--no-lock', '--repo', '/repository', '--password-file', '/secret/password', *native]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--password-file', type=Path, required=True)
    parser.add_argument('--restic', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--runner-environment', required=True)
    args = parser.parse_args()
    root = args.root.absolute(); reports = args.reports.resolve(strict=True)
    binary = args.restic.resolve(strict=True); key = args.password_file.absolute()
    if (root.resolve() != root or root.name != 'run' or root.parent.parent != Path('/tmp')
            or not re.fullmatch(r'native-foundation-offhost-ci\.[A-Za-z0-9]+', root.parent.name)
            or reports != root.parent / 'reports' or key != root.parent / 'private/password'
            or key.resolve() != key):
        raise ValueError('unexpected owned runner paths')
    if args.runner_environment != 'github-hosted' or not args.run_id.isdigit() or not re.fullmatch('[0-9a-f]{40}', args.source_sha):
        raise ValueError('hosted-runner provenance missing')
    info = key.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or not 1 <= info.st_size <= 256:
        raise ValueError('fixture password must be a nonempty regular mode0600 file')
    plan = load(HERE / 'plan.json')
    hosted_plan = load(HERE / 'hosted-plan.json')
    if hosted_plan['preparation_plan_sha256'] != digest(HERE/'plan.json'):
        raise ValueError('hosted correction does not reference the frozen preparation plan')
    verify_sources(hosted_plan)
    if digest(binary) != plan['binary_sha256']:
        raise ValueError('native binary differs from frozen verified pin')
    data = load(HERE / 'input.json')
    if (digest(HERE/'repository.json') != data['repository_envelope_sha256']
            or digest(HERE/'repository-manifest.json') != data['repository_manifest_sha256']
            or data['source_parent'] != plan['source_parent']
            or len(data['snapshots']) != 2 or len(set(data['snapshots'])) != 2
            or any(not re.fullmatch('[0-9a-f]{64}', s) for s in data['snapshots'])):
        raise ValueError('frozen export input differs')
    root.mkdir(mode=0o700)
    # Native user-namespace UID1000 maps to this recorder's outer UID0. Only
    # these new, validated private paths receive that ownership, retaining0600.
    os.chown(key.parent, 0, 0)
    os.chown(key, 0, 0)
    staged_binary = root / 'restic'; shutil.copyfile(binary, staged_binary); staged_binary.chmod(0o755)
    staged_probe = root / 'probe.py'; shutil.copyfile(HERE/'probe.py', staged_probe); staged_probe.chmod(0o644)
    host_net = os.readlink('/proc/self/ns/net')
    host_mount = os.readlink('/proc/self/ns/mnt')
    report = {'schema_version':1, 'status':'started', 'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'One fresh GitHub-hosted Ubuntu runner restores two exact synthetic snapshots using a separately delivered fixture password.',
        'run_id':args.run_id,'source_sha':args.source_sha,'runner_environment':args.runner_environment,
        'binary_sha256':digest(binary),'input_sha256':digest(HERE/'input.json'),
        'plan_sha256':digest(HERE/'plan.json'), 'snapshots':data['snapshots'],
        'hosted_plan_sha256':digest(HERE/'hosted-plan.json'),
        'host_network_namespace':host_net,'host_mount_namespace':host_mount,
        'commands':[], 'checks':{}, 'limitations':plan['limitations'],
        'sanitization':'Owned runner paths are replaced by role placeholders; native source username in restore banners is replaced. Raw stdout/stderr SHA256 and lengths are retained. Raw streams are held in memory only; password contents are neither read by this recorder nor returned.',
        'model_calls':0,'exact_causal_lifetime_provider_tokens_saved':None}
    expected = load(HERE / 'repository-manifest.json')
    def call(label, native, supplied_key, expected_exit):
        output = root / label; output.mkdir(mode=0o755)
        argv = sandbox_command(staged_binary, root/'repository', supplied_key, output, staged_probe, native)
        replacements = [(str(root),'$OWNED_RUN'), (str(binary),'$RESTIC'),(str(HERE),'$BLUEPRINT'),(str(key),'$FIXTURE_PASSWORD_FILE')]
        def public(value):
            value = sanitize(value)
            for old, new in replacements: value = value.replace(old, new)
            return value
        record = {'id':label,'argv':[public(x) for x in argv], 'expected_exit':expected_exit}
        started = time.monotonic()
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                timeout=120, env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}, cwd=root)
            record.update(exit_code=result.returncode, timeout=False)
            for name, raw in [('stdout', result.stdout),('stderr', result.stderr)]:
                record[name] = {'text':public(raw.decode(errors='replace')),
                                'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw)}
        except subprocess.TimeoutExpired as error:
            record.update(exit_code=None, timeout=True)
            for name, raw in [('stdout', error.stdout or b''),('stderr', error.stderr or b'')]:
                record[name] = {'text':public(raw.decode(errors='replace')),
                                'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw)}
        record['seconds'] = round(time.monotonic() - started, 3)
        report['commands'].append(record)
        save(reports/'receipt.json', report)
        if record['exit_code'] != expected_exit or record['timeout']:
            raise ValueError('native isolated command failed its expected exit: ' + label)
        namespace = load(output / 'namespace.json')
        if namespace['network_namespace'] == host_net or namespace['mount_namespace'] == host_mount:
            raise ValueError('native process did not enter isolated namespaces')
        if namespace['uid'] != 1000 or set(namespace['environment_keys']) != {'HOME','PATH','PWD','LANG','PYTHONDONTWRITEBYTECODE'}:
            raise ValueError('native process environment differs from frozen scope')
        record['namespace'] = namespace
        if repository_manifest(root/'repository') != expected:
            raise ValueError('native operation changed input ciphertext')
        return output
    try:
        decode_repository(load(HERE/'repository.json'), expected, root/'repository')
        report['checks']['ciphertext_exact_before_restore'] = True
        wrong = root / 'wrong-password'; wrong.write_text('deliberately-invalid-offhost-fixture-password\n'); wrong.chmod(0o600)
        output = call('wrong-password', ['restore',data['snapshots'][1]+':'+data['source_parent'],'--target','/out/restore','--verify'], wrong, 12)
        target = output / 'restore'
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise ValueError('wrong password produced restored files')
        report['checks']['wrong_password_exit12_no_files'] = True
        call('check-read-data', ['check','--read-data'], key, 0)
        report['checks']['native_read_all_data'] = True
        for number, snapshot in enumerate(data['snapshots'], 1):
            output = call('restore-' + str(number), ['restore',snapshot+':'+data['source_parent'],'--target','/out/restore','--verify'], key, 0)
            actual = verify_restore(output/'restore', number)
            save(reports / f'restored-{number}.json', actual)
            report['checks'][f'snapshot_{number}_complete_oracle'] = True
        report['checks']['ciphertext_unchanged_after_all_operations'] = repository_manifest(root/'repository') == expected
        report['checks']['all_native_operations_network_and_mount_isolated'] = True
        report['status'] = 'qualified-synthetic-independent-host-restore'
    except Exception as error:
        report['status'] = 'failed'
        report['failure'] = {'type':type(error).__name__,'message':sanitize(str(error)).replace(str(root),'$OWNED_RUN')}
    finally:
        # Only this invocation-created, validated root is removed; the secret is
        # separately removed by the workflow's always-run private-file cleanup.
        shutil.rmtree(root)
        report['checks']['owned_native_runtime_removed'] = not root.exists()
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(reports/'receipt.json', report)
    print(json.dumps({'status':report['status'],'commands':len(report['commands']),'checks':report['checks']}))
    return report['status'] != 'qualified-synthetic-independent-host-restore'


if __name__ == '__main__':
    sys.exit(main())
