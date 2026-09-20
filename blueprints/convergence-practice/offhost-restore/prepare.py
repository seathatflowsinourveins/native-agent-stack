"""One owned synthetic preparation and native neutral-key export; never print a password."""
from __future__ import annotations
import base64
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
from verify import BASELINE, HERE, digest, load, repository_manifest, verify_sources

ROOT = Path('/tmp/native-foundation-offhost-20260920')


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restic', type=Path, required=True)
    binary = parser.parse_args().restic.resolve(strict=True)
    plan = load(HERE / 'plan.json')
    verify_sources(plan)
    if digest(binary) != plan['binary_sha256']:
        raise ValueError('installed native binary differs from accepted pin')
    ROOT.mkdir(mode=0o700)
    frozen = ROOT / 'frozen-sources'; frozen.mkdir(mode=0o700)
    checkout = HERE.parents[2]
    for item in plan['frozen_sources']:
        dest = frozen / item['path']; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checkout / item['path'], dest)
    shutil.copyfile(HERE / 'plan.json', frozen / 'offhost-plan.json')
    save(ROOT / 'freeze.json', {'plan_sha256': digest(HERE / 'plan.json'),
                               'binary_sha256': digest(binary), 'sources': plan['frozen_sources']})
    private = ROOT / 'commands'; private.mkdir(mode=0o700)
    prep = ROOT / 'preparation'
    username = pwd.getpwuid(os.getuid()).pw_name
    hostname = socket.gethostname()
    def sanitized(value):
        return value.replace(str(binary), '$RESTIC').replace(str(checkout), '$CHECKOUT').replace(username, '$SOURCE_USER').replace(hostname, '$SOURCE_HOST')
    commands = []
    def call(label, argv, cwd=ROOT):
        started = datetime.now(timezone.utc).isoformat()
        timed_out = False
        try:
            result = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=600 if label == 'unchanged-corrected-prepare' else 120,
                                    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'})
            out, err, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            out, err, code = error.stdout or b'', error.stderr or b'', None
            timed_out = True
        streams = {}
        for name, raw in [('stdout', out), ('stderr', err)]:
            path = private / (label + '.' + name); path.write_bytes(raw); path.chmod(0o600)
            streams[name] = {'text': sanitized(raw.decode(errors='replace')), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes':len(raw)}
        commands.append({'id':label,'argv':[sanitized(str(a)) for a in argv], 'started_at_utc':started,
                         'exit_code':code, 'timeout':timed_out, **streams})
        save(ROOT / 'commands.json', commands)
        if code != 0 or timed_out:
            raise RuntimeError('native preparation failed: ' + label)
        return out
    call('unchanged-corrected-prepare', [sys.executable, str(BASELINE / 'run.py'), 'prepare', '--run-dir', str(prep), '--restic', str(binary)])
    prepared = load(prep / 'receipt.json')
    if prepared['status'] != 'prepared-awaiting-fresh-channel' or len(prepared['snapshots']) != 2:
        raise ValueError('native synthetic preparation did not pass')
    before = repository_manifest(prep / 'repository')
    save(ROOT / 'before-neutral-key-manifest.json', before)
    original_keys = [p.name for p in (prep / 'repository/keys').iterdir()]
    if len(original_keys) != 1:
        raise ValueError('new synthetic repository has unexpected key count')
    common = [str(binary), '--no-cache', '--repo', str(prep / 'repository'), '--password-file', str(prep / 'password')]
    call('add-neutral-key', [*common, 'key', 'add', '--host', 'synthetic-offhost-restore', '--user', 'synthetic', '--new-password-file', str(prep / 'password')])
    new_keys = [p.name for p in (prep / 'repository/keys').iterdir() if p.name not in original_keys]
    if len(new_keys) != 1:
        raise ValueError('native neutral-key add did not create exactly one key')
    neutral = new_keys[0]
    neutral_record = load(prep / 'repository/keys' / neutral)
    if neutral_record.get('username') != 'synthetic' or neutral_record.get('hostname') != 'synthetic-offhost-restore':
        raise ValueError('neutral key metadata differs')
    raw = call('validate-neutral-key-before-removal', [*common, '--key-hint', neutral, 'snapshots', '--json'])
    if sorted(p['id'] for p in json.loads(raw)) != sorted(prepared['snapshots']):
        raise ValueError('new key cannot read the exact prepared snapshots')
    call('remove-only-original-new-fixture-key', [*common, '--key-hint', neutral, 'key', 'remove', original_keys[0]])
    call('final-export-read-all-data', [*common, '--key-hint', neutral, 'check', '--read-data'])
    after = repository_manifest(prep / 'repository')
    save(ROOT / 'after-neutral-key-manifest.json', after)
    if ([e for e in before if not e['path'].startswith('keys/')] != [e for e in after if not e['path'].startswith('keys/')]
            or [e['path'] for e in after if e['path'].startswith('keys/')] != ['keys/' + neutral]):
        raise ValueError('native neutral-key correction changed non-key ciphertext')
    public_commands = []
    for command in commands:
        copy = json.loads(json.dumps(command))
        # Decoded snapshot metadata includes the source username: retain only exact raw hashes publicly.
        if command['id'] == 'validate-neutral-key-before-removal':
            copy['stdout']['text'] = '[decoded snapshot metadata retained privately; exact two IDs verified]'
        public_commands.append(copy)
    save(HERE / 'repository-manifest.json', after)
    save(HERE / 'repository.json', {'schema_version':1, 'files':[
        {'path':e['path'],'base64':base64.b64encode((prep/'repository'/e['path']).read_bytes()).decode()} for e in after]})
    save(HERE / 'input.json', {'schema_version':1,'source_parent':str(prep), 'snapshots':prepared['snapshots'],
        'repository_manifest_sha256':digest(HERE/'repository-manifest.json'),
        'repository_envelope_sha256':digest(HERE/'repository.json'), 'key_metadata':{'username':'synthetic','hostname':'synthetic-offhost-restore'},
        'frozen_after_native_key_correction':True})
    save(HERE / 'source-receipt.json', {'schema_version':1,'status':'prepared-only-awaiting-independent-host-restore',
        'plan_sha256':digest(HERE/'plan.json'),'binary_sha256':digest(binary),
        'preparation_receipt_sha256':digest(prep/'receipt.json'),
        'before_neutral_key_manifest_sha256':digest(ROOT/'before-neutral-key-manifest.json'),
        'after_neutral_key_manifest_sha256':digest(ROOT/'after-neutral-key-manifest.json'),
        'preparation_receipt':prepared, 'commands':public_commands,
        'checks':{'new_synthetic_state_only':True,'unchanged_corrected_prepare':True,
                  'same_exact_snapshots_after_native_key_metadata_correction':True,
                  'all_non_key_ciphertext_unchanged':True,'private_password_not_exported':True},
        'sanitization':'Native source username/hostname and checkout/tool paths are replaced in command streams; decoded snapshot JSON is private with exact output hash retained. Ciphertext is byte exact; neutral key labels were created by native key add/remove before export freeze.',
        'limitations':plan['limitations']})
    print(json.dumps({'status':'prepared-only-awaiting-independent-host-restore','repository_files':len(after),
                      'repository_bytes':sum(e['bytes'] for e in after),'password_file':str(prep/'password'),'password_mode':'0600'}))


if __name__ == '__main__':
    main()
