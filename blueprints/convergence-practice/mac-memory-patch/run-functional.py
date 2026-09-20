#!/usr/bin/env python3
"""Original-scope synthetic Mac patch trial; no OS confinement claim or promotion."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import shutil
import sqlite3
import subprocess
import tarfile
import threading
import time
import urllib.request

HERE = Path(__file__).resolve().parent


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def tree_hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}


def payload(response):
    if 'error' in response or response.get('result', {}).get('isError'):
        raise ValueError('native failure is not an empty successful response')
    content = response['result']['content']
    if len(content) != 1 or content[0]['type'] != 'text':
        raise ValueError('unexpected native content shape')
    value = json.loads(content[0]['text'])
    if not isinstance(value, dict):
        raise ValueError('expected native object')
    return value


def rejected(response):
    return isinstance(response.get('error'), dict) or response.get('result', {}).get('isError') is True


class MCP:
    def __init__(self, argv, cwd, env, root, name, cleanup):
        self.root, self.name, self.records = root, name, []
        self.cleanup = cleanup
        self.err = (root / (name + '.stderr')).open('w')
        self.raw = (root / (name + '.stdout.jsonl')).open('w')
        self.proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.err, text=True)
        self.replies = queue.Queue()
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        try:
            for line in self.proc.stdout:
                self.raw.write(line)
                self.raw.flush()
                self.replies.put(json.loads(line))
        except Exception as exc:
            self.replies.put(exc)
        finally:
            self.replies.put(EOFError('native stdio closed'))

    def request(self, method, params):
        identity = len(self.records) + 1
        req = {'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params}
        self.proc.stdin.write(json.dumps(req) + '\n')
        self.proc.stdin.flush()
        deadline = time.monotonic() + 20
        while True:
            response = self.replies.get(timeout=max(.001, deadline-time.monotonic()))
            if isinstance(response, Exception):
                raise response
            if response.get('id') == identity:
                self.records.append({'request': req, 'response': response})
                save(self.root / (self.name + '.protocol.json'), self.records)
                return response
            if time.monotonic() >= deadline:
                raise TimeoutError('native response deadline')

    def initialize(self):
        response = self.request('initialize', {'protocolVersion': '2025-03-26',
            'capabilities': {}, 'clientInfo': {'name': 'mac-memory-patch-synthetic', 'version': '1'}})
        if 'error' in response:
            raise ValueError('initialization rejected')
        self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
        self.proc.stdin.flush()
        return response['result']

    def call(self, name, **args):
        return self.request('tools/call', {'name': name, 'arguments': args})

    def close(self):
        forced = False
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except (subprocess.TimeoutExpired, BrokenPipeError):
            forced = True
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.thread.join(timeout=2)
        self.err.close()
        self.raw.close()
        self.proc.stdout.close()
        result = {'phase': self.name, 'exit_code': self.proc.returncode,
                  'forced_termination': forced, 'reader_closed': not self.thread.is_alive(),
                  'owned_process_exited': self.proc.poll() is not None,
                  'protocol_requests': len(self.records)}
        self.cleanup.append(result)
        save(self.root / 'cleanup.json', self.cleanup)


def database_state(data):
    with sqlite3.connect((data / 'db/memory.sqlite').as_uri() + '?mode=ro', uri=True) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = ['sessions', 'observations', 'workstream_events', 'workstream_native_sessions', 'page_embeddings']
        if not set(required).issubset(tables):
            raise ValueError('missing no-capture/no-embedding tables')
        return {'integrity': db.execute('PRAGMA integrity_check').fetchone()[0],
                'forbidden_population': {t: db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in required},
                'v62_present': db.execute('SELECT count(*) FROM refinery_schema_history WHERE version=62').fetchone()[0] == 1,
                'missing_page_windows': db.execute('SELECT count(*) FROM pages WHERE valid_from IS NULL').fetchone()[0],
                'page_versions': db.execute('SELECT count(*) FROM pages').fetchone()[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--old-binary', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    prefix = args.prefix.expanduser().resolve()
    old = args.old_binary.expanduser().resolve(strict=True)
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('this recipe requires native Apple Silicon macOS')
    if not args.attempt.replace('-', '').isalnum() or prefix == Path.home() or prefix.is_relative_to(HERE):
        raise ValueError('choose a named new attempt and a private prefix outside the checkout')
    prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
    attempt = prefix / args.attempt
    attempt.mkdir(mode=0o700)
    (attempt / 'tmp').mkdir()
    pins = json.loads((HERE / 'pins.json').read_text())
    oracle = json.loads((HERE / 'oracle-functional.json').read_text())
    frozen = attempt / 'frozen'
    frozen.mkdir()
    for filename in ['run-functional.py', 'pins.json', 'oracle-functional.json', 'config.toml']:
        shutil.copyfile(HERE / filename, frozen / filename)
    frozen_hashes = tree_hashes(frozen)
    checks, cleanup = {}, []
    result = {'schema_version': 1, 'host_scope': 'macOS arm64 isolated synthetic qualification',
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'platform': {'macos': platform.mac_ver()[0], 'architecture': platform.machine(),
                           'python': platform.python_version()},
              'pins': pins, 'frozen_inputs': frozen_hashes, 'checks': checks,
              'cleanup': cleanup, 'production_promoted': False, 'production_state_opened': False,
              'model_invocation': False, 'enclosing_agent_usage': None}

    def check(name, value):
        checks[name] = bool(value)
        save(attempt / 'receipt.json', result)
        if not value:
            raise AssertionError(name)

    def command(name, argv, env=None):
        cp = subprocess.run(argv, cwd=attempt, env=env, capture_output=True, text=True, timeout=30)
        save(attempt / (name+'.command.private.json'), {'argv': list(map(str, argv)),
             'exit_code': cp.returncode, 'stdout': cp.stdout, 'stderr': cp.stderr})
        return cp

    try:
        check('baseline_binary_hash', sha(old) == pins['baseline_binary_sha256'])
        installation = prefix / 'distribution-2.3.2'
        if not installation.exists():
            installation.mkdir()
            for suffix, key in [('', 'archive_sha256'), ('.sha256', 'sidecar_sha256')]:
                url = pins['archive_url'] + suffix
                path = installation / ('ai-memory-macos-aarch64.tar.gz'+suffix)
                with urllib.request.urlopen(url, timeout=30) as response, path.open('xb') as target:
                    shutil.copyfileobj(response, target)
                check(key, sha(path) == pins[key])
            archive = installation / 'ai-memory-macos-aarch64.tar.gz'
            with tarfile.open(archive, 'r:gz') as tar:
                members = tar.getmembers()
                if any(Path(m.name).is_absolute() or '..' in Path(m.name).parts or
                       m.issym() or m.islnk() or not (m.isfile() or m.isdir()) for m in members):
                    raise ValueError('unsafe release archive')
                tar.extractall(installation / 'unpacked', members=members, filter='data')
        check('archive_hash', sha(installation / 'ai-memory-macos-aarch64.tar.gz') == pins['archive_sha256'])
        sidecar = installation / 'ai-memory-macos-aarch64.tar.gz.sha256'
        check('sidecar_hash', sha(sidecar) == pins['sidecar_sha256'])
        check('sidecar_names_exact_archive', sidecar.read_text().split() == [pins['archive_sha256'], 'ai-memory-macos-aarch64.tar.gz'])
        new = installation / 'unpacked/ai-memory'
        check('candidate_binary_hash', sha(new) == pins['binary_sha256'])
        check('bundled_mit_license_hash', sha(installation / 'unpacked/LICENSE') == pins['license_sha256'])
        cp = command('file', ['/usr/bin/file', str(new)])
        check('native_arm64_format', cp.returncode == 0 and 'Mach-O 64-bit executable arm64' in cp.stdout)
        cp = command('codesign-verify', ['/usr/bin/codesign', '--verify', '--strict', '--verbose=2', str(new)])
        check('native_signature_integrity', cp.returncode == 0)
        detail = command('codesign-display', ['/usr/bin/codesign', '-dv', '--verbose=4', str(new)])
        gatekeeper = command('gatekeeper', ['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=4', str(new)])
        result['signature_assessment'] = {'integrity_exit': cp.returncode,
            'ad_hoc': 'Signature=adhoc' in detail.stderr,
            'gatekeeper_exit': gatekeeper.returncode,
            'gatekeeper_accepted': gatekeeper.returncode == 0,
            'overrides_or_signature_changes': False,
            'gatekeeper_summary': 'rejected: no usable signature' if 'no usable signature' in gatekeeper.stderr else
                                  ('accepted' if gatekeeper.returncode == 0 else 'rejected; raw assessment retained privately')}
        env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(Path.home()),
               'LANG': 'en_US.UTF-8', 'TMPDIR': str(attempt / 'tmp')}
        sandbox = []
        result['os_filesystem_network_confinement'] = 'not established; prior restricted-profile attempt failed'
        result['environment_keys'] = sorted(env)
        result['native_arguments_template'] = ['<versioned-binary>', '--data-dir', '<attempt>/data', '--config', '<attempt>/frozen/config.toml', 'serve', '--transport', 'stdio', '--no-watcher', '--workspace', oracle['workspace'], '--project', 'alpha']
        versions = {}
        for name, binary, expected in [('baseline', old, '2.3.1'), ('candidate', new, '2.3.2')]:
            cp = command(name+'-version', sandbox+[str(binary), '--version'], env)
            versions[name] = cp.stdout.strip()
            check(name+'_native_version', cp.returncode == 0 and versions[name] == 'ai-memory '+expected)
        result['versions'] = versions
        config = frozen / 'config.toml'
        data = attempt / 'data'
        workspace = oracle['workspace']

        def start(name, binary):
            m = MCP(sandbox + [str(binary), '--data-dir', str(data), '--config', str(config),
                'serve', '--transport', 'stdio', '--no-watcher', '--workspace', workspace,
                '--project', 'alpha'], attempt, env, attempt, name, cleanup)
            return m

        def initialize(m, version):
            info = m.initialize()
            check(m.name+'_server_version', info['serverInfo']['version'] == version)
            listed = m.request('tools/list', {})
            names = sorted(t['name'] for t in listed['result']['tools'])
            result.setdefault('tool_names_by_phase', {})[m.name] = names
            check(m.name+'_four_tools_available', set(oracle['required_tools']).issubset(names))

        def call(m, tool, project='alpha', **arguments):
            return m.call(tool, workspace=workspace, project=project, **arguments)

        def verify_scopes(m, alpha_body, alpha_marker):
            for key, body, marker in [('alpha', alpha_body, alpha_marker), ('beta', oracle['beta']['body'], oracle['beta']['marker'])]:
                item = oracle[key]
                read = payload(call(m, 'memory_read_page', project=key, path=item['path']))
                check(m.name+'_'+key+'_body', read['body'] == body)
                query = payload(call(m, 'memory_query', project=key, query=marker, explain=True))
                check(m.name+'_'+key+'_fts', [h['path'] for h in query['hits']] == [item['path']] and 'fts' in query['streams_active'])
                other = 'beta' if key == 'alpha' else 'alpha'
                query = payload(call(m, 'memory_query', project=other, query=marker))
                check(m.name+'_'+key+'_negative_query', query['hits'] == [])
                negative = call(m, 'memory_read_page', project=other, path=item['path'])
                check(m.name+'_'+key+'_negative_read', rejected(negative))
            status = payload(call(m, 'memory_status'))
            check(m.name+'_no_capture_status', status['counts']['sessions'] == 0 and status['counts']['observations'] == 0)

        m = start('baseline', old)
        try:
            initialize(m, '2.3.1')
            for key in ['alpha', 'beta']:
                item = oracle[key]
                payload(call(m, 'memory_write_page', project=key, path=item['path'], body=item['body']))
            verify_scopes(m, oracle['alpha']['body'], oracle['alpha']['marker'])
        finally:
            m.close()
        baseline_state = database_state(data)
        result['baseline_database'] = baseline_state
        check('baseline_integrity_and_v62', baseline_state['integrity'] == 'ok' and baseline_state['v62_present'] and baseline_state['missing_page_windows'] == 0)
        baseline = attempt / 'frozen-baseline-store'
        shutil.copytree(data, baseline)
        baseline_hashes = tree_hashes(baseline)
        save(attempt / 'baseline-store-hashes.private.json', baseline_hashes)
        m = start('candidate', new)
        try:
            initialize(m, '2.3.2')
            verify_scopes(m, oracle['alpha']['body'], oracle['alpha']['marker'])
            negative = call(m, 'memory_write_page', path=oracle['reserved_path'], body='Synthetic rejected page.\n')
            check('candidate_git_reserved_path_rejected', rejected(negative))
            item = oracle['unicode']
            payload(call(m, 'memory_write_page', path=item['path'], body=item['body']))
            check('candidate_unicode_exact_read', payload(call(m, 'memory_read_page', path=item['path']))['body'] == item['body'])
            payload(call(m, 'memory_write_page', path=oracle['alpha']['path'], body=oracle['updated_alpha']['body']))
        finally:
            m.close()
        m = start('candidate-restart', new)
        try:
            initialize(m, '2.3.2')
            verify_scopes(m, oracle['updated_alpha']['body'], oracle['updated_alpha']['marker'])
            item = oracle['unicode']
            check('restart_unicode_exact_body', payload(call(m, 'memory_read_page', path=item['path']))['body'] == item['body'])
            q = payload(call(m, 'memory_query', query=item['marker'], explain=True))
            check('restart_unicode_fts', [h['path'] for h in q['hits']] == [item['path']] and 'fts' in q['streams_active'])
            check('superseded_marker_absent', payload(call(m, 'memory_query', query=oracle['alpha']['marker']))['hits'] == [])
        finally:
            m.close()
        state = database_state(data)
        result['candidate_database'] = state
        check('candidate_integrity_and_v62', state['integrity'] == 'ok' and state['v62_present'] and state['missing_page_windows'] == 0)
        check('no_capture_or_embedding_rows', all(n == 0 for n in state['forbidden_population'].values()))
        check('no_model_files', not (data/'models').exists() or not any(p.is_file() for p in (data/'models').rglob('*')))
        check('baseline_snapshot_unchanged', baseline_hashes == tree_hashes(baseline))
        check('frozen_inputs_unchanged', frozen_hashes == tree_hashes(frozen))
        check('binary_hashes_unchanged', sha(old) == pins['baseline_binary_sha256'] and sha(new) == pins['binary_sha256'])
        check('all_owned_processes_cleanly_exited', len(cleanup) == 3 and all(x['exit_code'] == 0 and not x['forced_termination'] and x['owned_process_exited'] and x['reader_closed'] for x in cleanup))
        result['passed'] = True
    except Exception as exc:
        result.update(passed=False, failure={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['private_log_hashes'] = {p.name: sha(p) for p in sorted(attempt.glob('*.json*')) if p.name != 'receipt.json'}
        save(attempt/'receipt.json', result)
        print(json.dumps({'passed': result.get('passed', False), 'checks': len(checks),
                          'failed_checks': [k for k,v in checks.items() if not v], 'cleanup': cleanup}))


if __name__ == '__main__':
    main()
