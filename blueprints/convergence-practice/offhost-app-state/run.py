"""Compose pinned native application recovery; this is a local integration check.

Only hosted, explicitly owned synthetic state is used. Existing native helpers
provide MCP, memory preparation, Restic installation and ciphertext decoding.
"""
from __future__ import annotations
import argparse
import base64
import contextlib
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
MEMORY = HERE.parent / 'wsl-memory-maintenance'
AUTH_VALUE = re.compile(r'''(?ix)(?:\bBearer\s+|\b(?:authorization|auth[_-]?token|bearer[_-]?token|token|api[_-]?key|encryption[_-]?key|password)["']?\s*[:=]\s*["']?(?:Bearer\s+)?)([A-Za-z0-9_+/=-]{16,})''')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


transfer = module('app_transfer', HERE.parent / 'offhost-restore/verify.py')
memory = module('app_memory', MEMORY / 'run.py')
sha = transfer.digest
load = transfer.load


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def public_auth_filter(value):
    return AUTH_VALUE.sub(lambda match: match.group(0).replace(match.group(1), '$REDACTED_AUTH_VALUE'), value)


def proof_files(raw, secrets):
    """Explicit flat command/protocol evidence allowlist; never app/auth files."""
    files = []
    for path in sorted(raw.iterdir()):
        if (not stat.S_ISREG(path.lstat().st_mode) or path.suffix not in
                {'.json', '.jsonl', '.stdout', '.stderr', '.response', '.xml'}
                or re.search(r'(?:^|[._-])(?:auth|credentials|encryption[_-]?key)(?:[._-]|$)', path.name)):
            raise ValueError('raw proof contains unsupported file or nested state')
        data = path.read_bytes()
        if any(secret.encode() in data for secret in secrets) or AUTH_VALUE.search(data.decode('utf-8', errors='replace')):
            raise ValueError('authentication material detected in native proof; no upload')
        files.append(path)
    return files


def validate_source(folder, identity, plan_sha256, record_sha256):
    folder = Path(folder)
    if folder.resolve() != folder or {p.name for p in folder.iterdir()} != {'source.json', 'manifest.json', 'repository.json'}:
        raise ValueError('unexpected transfer artifact members')
    if any(not stat.S_ISREG(p.lstat().st_mode) for p in folder.iterdir()):
        raise ValueError('transfer artifact contains unsupported member type')
    if sha(folder / 'source.json') != record_sha256:
        raise ValueError('platform-bound source record checksum differs')
    original = load(folder / 'source.json')
    if (original['status'] != 'source-prepared-only' or original['plan_sha256'] != plan_sha256
            or original['identity']['head_sha'] != identity['head_sha']
            or original['identity']['run_id'] != identity['run_id']
            or original['identity']['run_attempt'] != identity['run_attempt']
            or original['identity']['runner_environment'] != 'github-hosted'
            or original['identity']['boot_id_sha256'] == identity['boot_id_sha256']
            or original['identity']['job'] == identity['job']):
        raise ValueError('source/destination identity or frozen plan boundary differs')
    if sorted(row['name'] for row in original['files']) != ['memory.tar.gz', 'qdrant.snapshot']:
        raise ValueError('unexpected application archive set')
    if sha(folder / 'manifest.json') != original['manifest_sha256'] or sha(folder / 'repository.json') != original['envelope_sha256']:
        raise ValueError('transferred ciphertext differs')
    return original


def owned_root(path):
    path = Path(path).absolute()
    if (path.parent != Path('/tmp') or not re.fullmatch(r'native-offhost-app\.[A-Za-z0-9_]+', path.name)
            or path.resolve() != path or not path.is_dir() or path.stat().st_uid != os.getuid()):
        raise ValueError('expected this job-owned real /tmp root')
    return path


def f32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def canonical_points(points):
    result = []
    for point in points:
        vector = point['vector']
        vector = {'': vector} if isinstance(vector, list) else vector
        vectors = {}
        for name, value in vector.items():
            if isinstance(value, list):
                vectors[name] = [f32(x) for x in value]
            else:
                if set(value) != {'indices', 'values'} or len(value['indices']) != len(value['values']):
                    raise ValueError('unexpected sparse vector')
                pairs = sorted(zip(value['indices'], value['values']))
                vectors[name] = {'indices': [x[0] for x in pairs], 'values': [f32(x[1]) for x in pairs]}
        result.append({'id': point['id'], 'payload': point.get('payload') or {}, 'vector': vectors})
    if len({p['id'] for p in result}) != len(result):
        raise ValueError('duplicate point identity')
    return sorted(result, key=lambda p: p['id'])


def check_rust_tests(output, names):
    actual = re.findall(r'^test (\S+) \.\.\. (\S+)$', output, flags=re.M)
    if sorted(actual) != sorted((name, 'ok') for name in names):
        raise ValueError('selected Rust tests missing, duplicated, ignored or failed')
    if 'skipping GNU sparse' in output or not re.search(r'test result: ok\. \d+ passed; 0 failed; 0 ignored;', output):
        raise ValueError('upstream test body skipped or terminal result absent')


def check_pytest(path):
    cases = ET.parse(path).getroot().findall('.//testcase')
    expected = {(name, value) for name in ('test_collection_snapshot_operations', 'test_full_snapshot_operations')
                for value in ('False', 'True')}
    actual = set()
    for case in cases:
        match = re.fullmatch(r'(test_\w+)\[(False|True)\]', case.attrib['name'])
        if not match or len(case) or match.groups() in actual:
            raise ValueError('unexpected, duplicated or nonpassing upstream pytest case')
        actual.add(match.groups())
    if actual != expected:
        raise ValueError('selected upstream pytest cases missing')


class Trial:
    def __init__(self, root, phase):
        self.root, self.phase = owned_root(root), phase
        self.reports, self.raw = self.root / 'reports', self.root / 'raw'
        self.reports.mkdir(exist_ok=True); self.raw.mkdir(exist_ok=True)
        self.plan = load(HERE / 'plan.json')
        self.pins = load(HERE / 'upstream.json')
        self.record = {'schema_version': 1, 'phase': phase, 'status': 'started', 'commands': [],
                       'started_at_utc': self.now(), 'provenance_type': 'local-integration',
                       'plan_sha256': sha(HERE / 'plan.json'), 'cleanup': [],
                       'limitations': self.plan['limitations']}
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(self.root / 'home'),
                    'LANG': 'C.UTF-8', 'TMPDIR': str(self.root / 'tmp'),
                    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'}
        for name in ('home', 'tmp'): (self.root / name).mkdir(exist_ok=True)
        self.secrets = []
        self.persist()

    @staticmethod
    def now(): return datetime.now(timezone.utc).isoformat()

    def sanitize(self, value):
        text = str(value)
        for old, new in [(str(self.root), '$OWNED_RUN'), (str(CHECKOUT), '$CHECKOUT'),
                         (str(Path.home()), '$RUNNER_HOME'), (socket.gethostname(), '$RUNNER_HOST')]:
            text = text.replace(old, new)
        # Snapshot banners contain the source's username, not application data.
        text = text.replace(getpass.getuser() + '@', '$RUNNER_USER@')
        for secret in self.secrets:
            if secret: text = text.replace(secret, '$FIXTURE_SECRET')
        return public_auth_filter(text)

    def persist(self):
        save(self.raw / (self.phase + '-commands.json'), self.record)
        save(self.reports / (self.phase + '.json'), json.loads(self.sanitize(json.dumps(self.record))))

    def stream(self, label, kind, raw):
        path = self.raw / (label + '.' + kind)
        path.write_bytes(raw)
        public = self.reports / (label + '.' + kind)
        public.write_text(self.sanitize(raw.decode('utf-8', errors='replace')))
        return {'raw_sha256': sha(path), 'raw_bytes': len(raw), 'public_path': public.name,
                'public_sha256': sha(public), 'public_bytes': public.stat().st_size,
                'sanitization': 'Owned root, checkout, runner home/hostname/username and known fixture-secret substitution; exact original streams retained only in encrypted proof.'}

    def call(self, label, argv, cwd=None, env=None, timeout=120, expected=0):
        cwd = Path(cwd or self.root)
        record = {'id': label, 'argv': [str(v) for v in argv], 'cwd': str(cwd),
                  'started_at_utc': self.now(), 'timeout_seconds': timeout, 'launched': True}
        start = time.monotonic()
        process = None
        try:
            process = subprocess.Popen([str(v) for v in argv], cwd=cwd, env=env or self.env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            out, err = process.communicate(timeout=timeout); code = process.returncode
            record.update(exit_code=code, timed_out=False)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGTERM)
            try: out, err = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); out, err = process.communicate(timeout=5)
            code = None
            record.update(exit_code=process.returncode, timed_out=True, owned_process_group_signals_sent=True)
        except OSError as error:
            out, err, code = b'', b'', None
            record.update(exit_code=None, timed_out=False, launched=False,
                          launch_error={'type': type(error).__name__, 'errno': error.errno, 'message': str(error)})
        record.update(finished_at_utc=self.now(), seconds=round(time.monotonic() - start, 6),
                      stdout=self.stream(label, 'stdout', out), stderr=self.stream(label, 'stderr', err))
        self.record['commands'].append(record); self.persist()
        if code != expected: raise RuntimeError('native command failed: ' + label)
        return out.decode()

    def request(self, label, method, route, body=None, port=6333):
        url = f'http://127.0.0.1:{port}' + route
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method,
                                         headers={'Content-Type': 'application/json'})
        record = {'id': label, 'method': method, 'url': url, 'body': body,
                  'started_at_utc': self.now(), 'timeout_seconds': 30}
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw, code = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, code = error.read(), error.code
        except OSError as error:
            raw, code = b'', None
            record['error'] = {'type': type(error).__name__, 'message': str(error)}
        record.update(finished_at_utc=self.now(), http_status=code,
                      response=self.stream(label, 'response', raw))
        self.record['commands'].append(record); self.persist()
        if code != 200: raise RuntimeError('native HTTP request failed: ' + label)
        return raw

    def verify_frozen(self):
        for entry in self.plan['frozen_sources']:
            if sha(CHECKOUT / entry['path']) != entry['sha256']:
                raise ValueError('frozen local source differs: ' + entry['path'])

    def identity(self):
        if os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
            raise ValueError('fresh GitHub-hosted runner required')
        return {'run_id': os.environ['GITHUB_RUN_ID'], 'run_attempt': os.environ['GITHUB_RUN_ATTEMPT'],
                'head_sha': os.environ['GITHUB_SHA'], 'job': os.environ['GITHUB_JOB'],
                'runner_environment': 'github-hosted',
                'boot_id_sha256': sha('/proc/sys/kernel/random/boot_id')}

    def password(self):
        path = self.root / 'private/password'
        if (not stat.S_ISREG(path.lstat().st_mode) or stat.S_IMODE(path.stat().st_mode) != 0o600
                or path.resolve() != path or path.stat().st_uid != os.getuid()):
            raise ValueError('fixture password must be owned regular 0600 file')
        value = path.read_text().strip()
        if not value or len(value) > 256: raise ValueError('missing or malformed fixture password')
        self.secrets.append(value)
        return path

    def restic(self, repository, password):
        return [str(self.root / 'tools/restic/restic'), '--no-cache', '--no-lock',
                '--repo', str(repository), '--password-file', str(password)]

    def new_repository(self, name, password):
        repo = self.root / name
        cmd = self.restic(repo, password)
        self.call(name + '-init', [*cmd, 'init', '--json'])
        old = {p.name for p in (repo / 'keys').iterdir()}
        if len(old) != 1: raise ValueError('new repository key count')
        self.call(name + '-neutral-key', [*cmd, 'key', 'add', '--host', 'synthetic-offhost-app',
                  '--user', 'synthetic', '--new-password-file', password])
        new = {p.name for p in (repo / 'keys').iterdir()} - old
        if len(new) != 1: raise ValueError('new neutral key count')
        key = new.pop()
        self.call(name + '-verify-key', [*cmd, '--key-hint', key, 'snapshots', '--json'])
        self.call(name + '-remove-initial-key', [*cmd, '--key-hint', key, 'key', 'remove', old.pop()])
        metadata = load(repo / 'keys' / key)
        if metadata['username'] != 'synthetic' or metadata['hostname'] != 'synthetic-offhost-app':
            raise ValueError('non-neutral public key metadata')
        return repo

    def export(self, repo, folder):
        folder.mkdir()
        manifest = transfer.repository_manifest(repo)
        save(folder / 'manifest.json', manifest)
        save(folder / 'repository.json', {'schema_version': 1, 'files': [
            {'path': row['path'], 'base64': base64.b64encode((repo / row['path']).read_bytes()).decode()}
            for row in manifest]})
        # Validate the reused decoder's finite object/size contract before upload.
        decoded = self.root / (folder.name + '-decoded-check')
        transfer.decode_repository(load(folder / 'repository.json'), manifest, decoded)
        shutil.rmtree(decoded)
        return {'manifest_sha256': sha(folder / 'manifest.json'),
                'envelope_sha256': sha(folder / 'repository.json')}

    @contextlib.contextmanager
    def qdrant(self, label, snapshot=None):
        state = self.root / label; state.mkdir()
        config = state / 'config.yaml'
        config.write_text('storage:\n  storage_path: ' + json.dumps(str(state / 'storage')) +
                          '\n  snapshots_path: ' + json.dumps(str(state / 'snapshots')) +
                          '\nservice:\n  host: 127.0.0.1\n  http_port: 6333\n  grpc_port: null\ncluster:\n  enabled: false\n')
        argv = [str(self.root / 'tools/qdrant'), '--config-path', str(config), '--disable-telemetry']
        if snapshot is not None: argv += ['--storage-snapshot', str(snapshot)]
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 6333))  # An occupied port is a failure, not another service.
        streams = [(self.raw / (label + '.' + name)).open('wb') for name in ('stdout', 'stderr')]
        process = None
        record = {'id': label, 'argv': argv, 'cwd': str(self.root), 'started_at_utc': self.now()}
        self.record['commands'].append(record); self.persist()
        try:
            process = subprocess.Popen(argv, cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=streams[0], stderr=streams[1])
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None: raise RuntimeError('owned Qdrant exited before readiness')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:6333/readyz', timeout=.5) as response:
                        if response.status == 200: break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() >= deadline: raise TimeoutError('owned Qdrant readiness deadline')
                    time.sleep(.1)
            yield
        finally:
            forced = False
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    forced = True; process.kill(); process.wait(timeout=5)
            for stream in streams: stream.close()
            for kind in ('stdout', 'stderr'):
                record[kind] = self.stream(label, kind, (self.raw / (label + '.' + kind)).read_bytes())
            with socket.socket() as probe: listener_closed = probe.connect_ex(('127.0.0.1', 6333)) != 0
            record.update(finished_at_utc=self.now(), exit_code=None if process is None else process.returncode)
            cleanup = {'process': label, 'exit_code': record['exit_code'], 'forced': forced,
                       'listener_closed': listener_closed}
            self.record['cleanup'].append(cleanup); self.persist()
            if forced or record['exit_code'] != 0 or not listener_closed:
                raise RuntimeError('owned Qdrant cleanup did not pass')


def install(trial):
    tools = trial.root / 'tools'; tools.mkdir()
    for name in ('memory', 'qdrant'):
        pin = trial.pins[name]
        archive = tools / (name + '.tar.gz')
        trial.call(name + '-download', ['curl', '--fail', '--location', '--silent', '--show-error',
                   '--max-time', '120', '--output', archive, pin['archive_url']], timeout=130)
        if sha(archive) != pin['archive_sha256']: raise ValueError('official archive checksum differs')
        with tarfile.open(archive) as tar:
            members = [m for m in tar if m.name.lstrip('./') == pin['archive_member']]
            if len(members) != 1 or not members[0].isfile(): raise ValueError('nonunique native executable')
            with tar.extractfile(members[0]) as stream: (tools / pin['binary_name']).write_bytes(stream.read())
        binary = tools / pin['binary_name']; binary.chmod(0o700)
        if sha(binary) != pin['binary_sha256']: raise ValueError('official executable checksum differs')
        output = trial.call(name + '-version', [binary, '--version'])
        if pin['version'] not in output: raise ValueError('native version differs')
    memory_pin = load(MEMORY / 'pins.json')
    trial.call('memory-sidecar', ['curl', '--fail', '--location', '--silent', '--show-error', '--max-time', '60',
               '--output', tools / 'memory.tar.gz.sha256', memory_pin['archive_url'] + '.sha256'])
    if sha(tools / 'memory.tar.gz.sha256') != memory_pin['sidecar_sha256']:
        raise ValueError('official memory sidecar differs')
    try:
        trial.call('restic-install', [sys.executable, HERE.parent / 'wsl-restore/install.py',
                   '--destination', tools / 'restic'], timeout=300)
    finally:
        report = tools / 'restic/installation.json'
        if report.exists():
            (trial.reports / 'restic-installation.json').write_text(trial.sanitize(report.read_text()))
    if sha(tools / 'restic/restic') != trial.pins['restic_binary_sha256']:
        raise ValueError('verified Restic executable differs')


def upstream(trial):
    trial.record['provenance_type'] = 'upstream-unmodified-selected-tests'
    for name in ('memory', 'qdrant'):
        spec = trial.pins[name]; source = trial.root / ('upstream-' + name)
        trial.call(name + '-git-init', ['git', 'init', '--quiet', source])
        trial.call(name + '-git-remote', ['git', 'remote', 'add', 'origin', spec['repository']], cwd=source)
        trial.call(name + '-git-fetch', ['git', 'fetch', '--quiet', '--depth', '1', 'origin', spec['source_commit']], cwd=source)
        trial.call(name + '-git-checkout', ['git', 'checkout', '--quiet', '--detach', 'FETCH_HEAD'], cwd=source)
        if trial.call(name + '-git-head', ['git', 'rev-parse', 'HEAD'], cwd=source).strip() != spec['source_commit']:
            raise ValueError('upstream commit differs')
        for item in spec['source_files']:
            if sha(source / item['path']) != item['sha256']: raise ValueError('upstream source hash differs')
    source = trial.root / 'upstream-memory'
    rustenv = trial.env | {k: os.environ[k] for k in ('RUSTUP_HOME', 'CARGO_HOME') if k in os.environ}
    rustenv['RUSTUP_TOOLCHAIN'] = '1.95.0'
    tar = trial.call('gnu-tar-prerequisite', ['tar', '--version'])
    if 'GNU tar' not in tar: raise ValueError('upstream sparse test would skip without GNU tar')
    trial.call('gzip-prerequisite', ['gzip', '--version'])
    version = trial.call('rust-version', ['rustc', '--version'], cwd=source, env=rustenv)
    if not version.startswith('rustc 1.95.'): raise ValueError('pinned Rust toolchain differs')
    for selection in trial.pins['memory']['test_selections']:
        output = trial.call(selection['id'], selection['command'], cwd=source, env=rustenv, timeout=1500)
        check_rust_tests(output + (trial.raw / (selection['id'] + '.stderr')).read_text(), selection['expected_tests'])
    source = trial.root / 'upstream-qdrant'; env = qdrant_env(trial)
    if trial.call('uv-version', ['uv', '--version'], env=env).strip() != 'uv 0.9.17':
        raise ValueError('upstream-selected UV version differs')
    trial.call('qdrant-lock-check', ['uv', '--project', source / 'tests', 'lock', '--check'], env=env)
    trial.call('qdrant-dependencies', ['uv', '--project', source / 'tests', 'sync', '--frozen'], env=env, timeout=300)
    trial.call('qdrant-private-network-tests', ['sudo', '--non-interactive', '/usr/bin/env', '-i',
               'PATH=' + trial.env['PATH'], 'HOME=' + trial.env['HOME'], 'LANG=C.UTF-8',
               'PARENT_NETWORK_NAMESPACE=' + os.readlink('/proc/self/ns/net'), 'unshare', '--net', '--',
               sys.executable, HERE / 'network.py', str(os.getuid()), str(os.getgid()),
               sys.executable, HERE / 'run.py', 'qdrant-tests', '--root', trial.root], timeout=330)
    if load(trial.reports / 'qdrant-tests.json')['status'] != 'passed':
        raise ValueError('unchanged Qdrant tests failed in private network')
    for name in ('memory', 'qdrant'):
        source = trial.root / ('upstream-' + name)
        trial.call(name + '-source-unchanged', ['git', 'diff', '--exit-code'], cwd=source)
    trial.record['accepted_upstream_cases'] = {'memory': 10, 'qdrant': 4}


def qdrant_tests(trial):
    trial.record['provenance_type'] = 'upstream-unmodified-release-target-adaptation'
    namespace = os.readlink('/proc/self/ns/net')
    if namespace == os.environ['PARENT_NETWORK_NAMESPACE']:
        raise ValueError('upstream helper requires a separate network namespace')
    interfaces = json.loads(trial.call('upstream-private-network-interfaces', ['/usr/sbin/ip', '-json', 'link', 'show']))
    trial.record['network_boundary'] = {'distinct_parent_namespace': True, 'interfaces': sorted(row['ifname'] for row in interfaces),
                                      'scope': 'Qdrant and unchanged upstream all-interface HTTP test helper share only the new loopback network.'}
    if trial.record['network_boundary']['interfaces'] != ['lo']:
        raise ValueError('unexpected network interface inside owned test namespace')
    source = trial.root / 'upstream-qdrant'; env = qdrant_env(trial)
    xml = trial.raw / 'qdrant-upstream.xml'
    with trial.qdrant('upstream-qdrant-service'):
        trial.call('qdrant-upstream-tests', ['uv', '--project', source / 'tests', 'run', '--no-sync', '--offline', 'pytest',
                   str(source / 'tests/openapi/test_snapshot.py') + '::test_collection_snapshot_operations',
                   str(source / 'tests/openapi/test_snapshot.py') + '::test_full_snapshot_operations',
                   '-v', '-p', 'no:cacheprovider', '--junitxml', xml], cwd=source, env=env, timeout=300)
    check_pytest(xml)
    (trial.reports / xml.name).write_text(trial.sanitize(xml.read_text()))


def qdrant_env(trial):
    source = trial.root / 'upstream-qdrant'
    return trial.env | {'PYTHONPATH': str(source / 'tests'),
                        'OPENAPI_FILE': str(source / 'docs/redoc/master/openapi.json'),
                        'QDRANT_HOST': 'http://127.0.0.1:6333', 'QDRANT_HOST_HEADERS': '{}'}


def qdrant_state(trial, phase):
    oracle = load(HERE / 'qdrant-oracle.json')
    prefix = '/collections/synthetic_offhost'
    collections = json.loads(trial.request(phase + '-collections', 'GET', '/collections'))['result']
    if collections != {'collections': [{'name': 'synthetic_offhost'}]}:
        raise ValueError('unexpected synthetic collection set')
    info = json.loads(trial.request(phase + '-collection', 'GET', prefix))['result']
    if info['status'] != 'green' or info['points_count'] != 10: raise ValueError('collection not ready or wrong size')
    points = []; offset = None
    for page in range(4):
        body = {'limit': 4, 'with_payload': True, 'with_vector': True}
        if offset is not None: body['offset'] = offset
        result = json.loads(trial.request(phase + '-scroll-' + str(page), 'POST', prefix + '/points/scroll', body))['result']
        points.extend(result['points']); offset = result['next_page_offset']
        if offset is None: break
    if offset is not None or canonical_points(points) != canonical_points(oracle['points']):
        raise ValueError('complete native points differ from frozen upstream fixture')
    queries = {}
    for name, query in oracle['queries'].items():
        result = json.loads(trial.request(phase + '-' + name, 'POST', prefix + '/points/query', query['body']))['result']['points']
        if [p['id'] for p in result] != query['ids'] or [f32(p['score']) for p in result] != [f32(s) for s in query['scores']]:
            raise ValueError('native query differs from independently frozen arithmetic oracle')
        queries[name] = result
        alias = json.loads(trial.request(phase + '-' + name + '-alias', 'POST',
                           '/collections/synthetic_offhost_alias/points/query', query['body']))['result']['points']
        if alias != result: raise ValueError('actual alias query differs')
    aliases = json.loads(trial.request(phase + '-aliases', 'GET', '/aliases'))['result']
    if aliases != {'aliases': [{'alias_name': 'synthetic_offhost_alias', 'collection_name': 'synthetic_offhost'}]}:
        raise ValueError('unexpected aliases')
    return {'points': sorted(points, key=lambda p: p['id']), 'config': info['config'],
            'payload_schema': info['payload_schema'], 'aliases': aliases, 'queries': queries}


def memory_queries(trial, data):
    oracle = load(HERE / 'memory-oracle.json'); cleanup = []
    argv = [str(trial.root / 'tools/ai-memory'), '--data-dir', str(data), '--config', str(MEMORY / 'config.toml'),
            'serve', '--transport', 'stdio', '--no-watcher', '--workspace', oracle['workspace'], '--project', 'alpha']
    record = {'id': 'restored-memory-stdio', 'argv': argv, 'cwd': str(trial.root),
              'started_at_utc': trial.now(), 'launched': False}
    trial.record['commands'].append(record); trial.persist()
    client = None
    facts = []
    try:
        client = memory.MCP(argv, trial.root, trial.env, trial.raw, 'restored-memory', cleanup)
        record['launched'] = True
        version = client.initialize()['serverInfo']['version']
        if version != '2.3.2': raise ValueError('restored memory server version differs')
        def call(tool, project='alpha', **args):
            args = {'workspace': oracle['workspace'], 'project': project, **args}
            response = client.call(tool, **args)
            facts.append({'tool': tool, 'arguments': args, 'response': response})
            save(trial.raw / 'memory-query-facts.json', facts)
            return memory.payload(response)
        for name, item in [('alpha', oracle['updated_alpha']), ('beta', oracle['beta']), ('alpha', oracle['unicode'])]:
            path = item.get('path', oracle['alpha']['path'])
            if call('memory_read_page', project=name, path=path)['body'] != item['body']:
                raise ValueError('restored memory body differs')
            found = call('memory_query', project=name, query=item['marker'], explain=True)
            if [h['path'] for h in found['hits']] != [path] or 'fts' not in found['streams_active']:
                raise ValueError('restored native lexical query differs')
            other = 'beta' if name == 'alpha' else 'alpha'
            if call('memory_query', project=other, query=item['marker'])['hits']:
                raise ValueError('cross-scope query leak')
            response = client.call('memory_read_page', workspace=oracle['workspace'], project=other, path=path)
            facts.append({'tool': 'memory_read_page', 'arguments': {'workspace': oracle['workspace'], 'project': other, 'path': path}, 'response': response})
            save(trial.raw / 'memory-query-facts.json', facts)
            error = response.get('error', {})
            if error.get('code') != -32603 or 'not found in resolved scope' not in error.get('message', ''):
                raise ValueError('cross-scope read did not reject')
        if call('memory_query', query=oracle['alpha']['marker'])['hits']:
            raise ValueError('obsolete marker present')
        counts = call('memory_status')['counts']
        if counts['sessions'] != 0 or counts['observations'] != 0: raise ValueError('unexpected captured history')
    finally:
        if client is not None: client.close()
        trial.record['cleanup'].extend(cleanup)
        record.update(finished_at_utc=trial.now(), exit_code=None if client is None else client.proc.returncode)
        for kind, name in [('stdout', 'restored-memory.stdout.jsonl'), ('stderr', 'restored-memory.stderr')]:
            path = trial.raw / name
            if path.exists(): record[kind] = trial.stream('restored-memory-stdio', kind, path.read_bytes())
        trial.persist()
        if any(row['exit_code'] != 0 or row['forced_termination'] for row in cleanup):
            raise RuntimeError('native memory process cleanup failed')
    state = memory.database_state(data)
    if state['integrity'] != 'ok' or not state['v62_present'] or state['missing_page_windows'] or any(state['forbidden_population'].values()):
        raise ValueError('restored memory database oracle failed')
    save(trial.reports / 'memory-query-facts.json', json.loads(trial.sanitize(json.dumps(facts))))
    return state


def safe_memory_archive(path):
    with tarfile.open(path) as archive:
        names = set()
        for entry in archive:
            name = entry.name
            if name in names or Path(name).is_absolute() or '..' in Path(name).parts or not (entry.isfile() or entry.isdir()):
                raise ValueError('unsafe native memory archive')
            allowed = name in {'wiki', 'db'} or name.startswith('wiki/') or (entry.isfile() and name in {'db/memory.sqlite', 'config.toml'})
            if not allowed: raise ValueError('unexpected native memory archive member')
            names.add(name)
            if name == 'config.toml' and entry.isfile():
                with archive.extractfile(entry) as stream:
                    if stream.read() != (MEMORY / 'config.toml').read_bytes():
                        raise ValueError('archive configuration is not the frozen secret-free fixture configuration')
        if 'db/memory.sqlite' not in names: raise ValueError('native memory database missing')


def source(trial):
    trial.record['identity'] = trial.identity()
    if load(trial.reports / 'upstream.json')['status'] != 'passed': raise ValueError('upstream tests have not passed')
    password = trial.password(); payload = trial.root / 'payload'; payload.mkdir()
    staged = trial.root / 'memory-fixture-source'; staged.mkdir()
    for name in ('run.py', 'pins.json', 'config.toml'): shutil.copyfile(MEMORY / name, staged / name)
    shutil.copyfile(HERE / 'memory-oracle.json', staged / 'oracle.json')
    memory_run = trial.root / 'memory-source'
    trial.call('native-memory-source', [sys.executable, staged / 'run.py', '--run-dir', memory_run,
               '--archive', trial.root / 'tools/memory.tar.gz', '--sidecar', trial.root / 'tools/memory.tar.gz.sha256'], timeout=180)
    result = load(memory_run / 'receipt.json')
    if not result['passed'] or result['restore']['status'] != 'passed' or result['backup']['status'] != 'passed':
        raise ValueError('native memory fixture did not pass backup and restore')
    if any(c['exit_code'] != 0 or c['forced_termination'] for c in result['cleanup']):
        raise ValueError('source memory cleanup differs')
    trial.record['cleanup'].extend(result['cleanup'])
    safe_memory_archive(memory_run / 'native-backup.tar.gz')
    shutil.copyfile(memory_run / 'native-backup.tar.gz', payload / 'memory.tar.gz')
    # Selected raw synthetic protocol/native results are recoverable in encrypted proof.
    for path in memory_run.iterdir():
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.stdout', '.stderr'):
            shutil.copyfile(path, trial.raw / ('source-memory-' + path.name))
    with trial.qdrant('source-qdrant'):
        source_path = trial.root / 'upstream-qdrant'
        trial.call('unchanged-qdrant-public-fixture', ['uv', '--project', source_path / 'tests', 'run', '--frozen', 'python', '-c',
                   "from openapi.helpers.collection_setup import basic_collection_setup; basic_collection_setup(collection_name='synthetic_offhost', on_disk_vectors=False)"],
                   cwd=source_path, env=qdrant_env(trial))
        for field, kind in [('city', 'keyword'), ('price', 'float')]:
            trial.request('source-index-' + field, 'PUT', '/collections/synthetic_offhost/index?wait=true',
                          {'field_name': field, 'field_schema': kind})
        trial.request('source-alias-create', 'POST', '/collections/aliases',
                      {'actions': [{'create_alias': {'collection_name': 'synthetic_offhost', 'alias_name': 'synthetic_offhost_alias'}}]})
        baseline = qdrant_state(trial, 'source')
        created = json.loads(trial.request('qdrant-native-snapshot-create', 'POST', '/snapshots?wait=true'))['result']
        name = created['name']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name): raise ValueError('unsafe native snapshot name')
        # Native binary archive stays private; only its encrypted representation is uploaded.
        trial.call('qdrant-native-snapshot-download', ['curl', '--fail', '--silent', '--show-error', '--max-time', '60',
                   '--output', payload / 'qdrant.snapshot', 'http://127.0.0.1:6333/snapshots/' + name])
        raw = (payload / 'qdrant.snapshot').read_bytes()
        if len(raw) != created['size'] or sha(payload / 'qdrant.snapshot') != created['checksum']:
            raise ValueError('native snapshot size/checksum differs')
        trial.record['qdrant_snapshot'] = {'method': 'GET', 'route': '/snapshots/{native-name}',
                                         'bytes': len(raw), 'sha256': sha(payload / 'qdrant.snapshot')}
        if qdrant_state(trial, 'source-after') != baseline: raise ValueError('source changed across native snapshot')
    files = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(payload.iterdir())]
    repo = trial.new_repository('app-repository', password); cmd = trial.restic(repo, password)
    output = trial.call('native-app-backup', [*cmd, 'backup', '--host', 'synthetic-offhost-app', '--json', payload], timeout=180)
    summaries = [json.loads(line) for line in output.splitlines() if json.loads(line).get('message_type') == 'summary']
    if len(summaries) != 1: raise ValueError('backup summary missing')
    snapshot = summaries[0]['snapshot_id']
    if not re.fullmatch('[0-9a-f]{64}', snapshot): raise ValueError('invalid exact snapshot ID')
    trial.call('native-app-full-check', [*cmd, 'check', '--read-data'], timeout=180)
    export = trial.root / 'transfer'; refs = trial.export(repo, export)
    source_record = {'schema_version': 1, 'status': 'source-prepared-only', 'identity': trial.record['identity'],
                     'plan_sha256': sha(HERE / 'plan.json'), 'snapshot': snapshot, 'source_parent': str(trial.root),
                     'files': files, 'memory_database': result['restored_database'], 'qdrant': baseline, **refs}
    save(export / 'source.json', source_record)
    trial.record['export'] = {'source_sha256': sha(export / 'source.json'), **refs}


def destination(trial):
    trial.record['identity'] = trial.identity(); password = trial.password()
    folder = trial.root / 'incoming'
    original = validate_source(folder, trial.record['identity'], sha(HERE / 'plan.json'), os.environ['SOURCE_RECORD_SHA256'])
    repo = trial.root / 'input-repository'; before = load(folder / 'manifest.json')
    transfer.decode_repository(load(folder / 'repository.json'), before, repo)
    snapshot = original['snapshot']; parent = original['source_parent']
    if not re.fullmatch('[0-9a-f]{64}', snapshot) or not re.fullmatch(r'/tmp/native-offhost-app\.[A-Za-z0-9_]+', parent):
        raise ValueError('invalid exact snapshot selection')
    wrong = trial.root / 'wrong-password'; wrong.write_text('deliberately-invalid-synthetic-fixture-password\n'); wrong.chmod(0o600)
    target = trial.root / 'wrong-target'
    trial.call('wrong-password-restore', [*trial.restic(repo, wrong), 'restore', snapshot + ':' + parent,
               '--target', target, '--verify'], expected=12)
    if target.exists() and any(target.rglob('*')): raise ValueError('wrong password restored files')
    cmd = trial.restic(repo, password)
    trial.call('received-repository-check', [*cmd, 'check', '--read-data'], timeout=180)
    target = trial.root / 'restored-archive'
    trial.call('exact-snapshot-restore', [*cmd, 'restore', snapshot + ':' + parent, '--target', target,
               '--verify', '--overwrite', 'never'], timeout=180)
    if {p.name for p in target.iterdir()} != {'payload'}: raise ValueError('unexpected restored root')
    payload = target / 'payload'
    actual = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(payload.iterdir()) if p.is_file() and not p.is_symlink()]
    if actual != original['files'] or len(list(payload.iterdir())) != len(actual): raise ValueError('native archives differ')
    safe_memory_archive(payload / 'memory.tar.gz')
    data = trial.root / 'restored-memory-data'
    trial.call('native-memory-restore', [trial.root / 'tools/ai-memory', '--data-dir', data,
               '--config', MEMORY / 'config.toml', 'restore', '--from', payload / 'memory.tar.gz'])
    state = memory_queries(trial, data)
    if state != original['memory_database']: raise ValueError('restored memory logical database differs')
    with trial.qdrant('destination-qdrant', payload / 'qdrant.snapshot'):
        if qdrant_state(trial, 'destination') != original['qdrant']:
            raise ValueError('restored complete Qdrant state/query/config differs')
    if transfer.repository_manifest(repo) != before: raise ValueError('input ciphertext changed')
    trial.record['checks'] = {'distinct_host_boot_identity': True, 'exact_archives': True,
                              'real_memory_queries': True, 'complete_qdrant_state_and_queries': True,
                              'ciphertext_unchanged': True}


def seal(trial):
    password = trial.password()
    # Freeze a copy before recording the encryption commands, avoiding self-reference.
    files = proof_files(trial.raw, trial.secrets)
    proof = trial.root / 'proof-input'; proof.mkdir()
    for path in files: shutil.copyfile(path, proof / path.name)
    repo = trial.new_repository('proof-repository', password)
    cmd = trial.restic(repo, password)
    trial.call('encrypt-native-proof', [*cmd, 'backup', '--host', 'synthetic-offhost-app', '--json', proof], timeout=180)
    trial.call('check-encrypted-proof', [*cmd, 'check', '--read-data'], timeout=180)
    trial.record['encrypted_proof'] = trial.export(repo, trial.root / 'encrypted-proof')


def cleanup(trial):
    private = trial.root / 'private'
    if private.exists() and private.resolve() != private:
        raise ValueError('private cleanup directory is not owned real path')
    key = private / 'password'
    if key.exists():
        if not stat.S_ISREG(key.lstat().st_mode): raise ValueError('unexpected password file type')
        key.unlink()
    # Only disposable paths created by this workflow; ciphertext exports/reports stay.
    names = ('private', 'home', 'tmp', 'tools', 'memory-source', 'memory-fixture-source', 'source-qdrant',
             'destination-qdrant', 'upstream-qdrant-service', 'upstream-memory', 'upstream-qdrant',
             'app-repository', 'input-repository', 'proof-repository', 'proof-input', 'wrong-password',
             'wrong-target', 'restored-archive', 'restored-memory-data', 'payload', 'rustup', 'cargo',
             'transfer-decoded-check', 'encrypted-proof-decoded-check', 'python-tools')
    for name in names:
        path = trial.root / name
        if path.is_symlink(): raise ValueError('unexpected runtime cleanup symlink')
        if path.is_dir(): shutil.rmtree(path)
        elif path.exists(): path.unlink()
    trial.record['checks'] = {'private_password_removed': not key.exists(),
                              'owned_runtime_removed': all(not (trial.root / n).exists() for n in names),
                              'scope': 'This job-owned prefix; encrypted proof and reports intentionally retained.'}
    shutil.rmtree(trial.raw)
    trial.raw.mkdir()
    trial.record['checks']['prior_unencrypted_raw_evidence_removed'] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('install', 'upstream', 'qdrant-tests', 'source', 'destination', 'seal', 'cleanup'))
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args(); trial = Trial(args.root, args.phase)
    try:
        if args.phase != 'cleanup': trial.verify_frozen()
        globals()[args.phase.replace('-', '_')](trial)
        trial.record['status'] = 'passed'
    except Exception as error:
        trial.record.update(status='failed', failure={'type': type(error).__name__, 'message': str(error)})
    finally:
        trial.record['finished_at_utc'] = trial.now(); trial.persist()
    print(json.dumps({'phase': args.phase, 'status': trial.record['status']}))
    return trial.record['status'] != 'passed'


if __name__ == '__main__': sys.exit(main())
