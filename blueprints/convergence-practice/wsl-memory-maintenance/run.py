#!/usr/bin/env python3
"""Linux synthetic memory maintenance trial; no production or client promotion."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import sqlite3
import subprocess
import tarfile
import threading
import time
import socket
import secrets

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
            'capabilities': {}, 'clientInfo': {'name': 'wsl-memory-maintenance-synthetic', 'version': '1'}})
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


def selected_fact(phase, tool, arguments, response):
    """Publish only synthetic arguments and fields required by the oracle."""
    fact = {'phase': phase, 'tool': tool, 'arguments': arguments}
    if 'error' in response:
        error = response['error']
        fact['error'] = {'code': error['code'], 'message': error['message']}
    elif response.get('result', {}).get('isError'):
        fact['tool_error'] = True
    else:
        value = payload(response)
        if tool == 'memory_read_page':
            fact['value'] = {'body': value['body']}
        elif tool == 'memory_query':
            fact['value'] = {'hits': [{'path': hit['path']} for hit in value['hits']]}
            if 'streams_active' in value:
                fact['value']['streams_active'] = value['streams_active']
        elif tool == 'memory_status':
            fact['value'] = {'counts': {k: value['counts'][k] for k in ['sessions', 'observations']}}
        else:
            fact['value'] = {'acknowledged': True}
    return fact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--sidecar', required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('Linux x86_64 required')
    os.umask(0o077)
    run = args.run_dir.expanduser().absolute()
    repo = next((p for p in HERE.parents if (p/'.git').exists()), HERE)
    if run == Path.home() or run.is_relative_to(repo) or any(p.is_symlink() for p in [run, *run.parents]):
        raise ValueError('new private run directory outside checkout required')
    run.mkdir(parents=False, mode=0o700)
    (run/'tmp').mkdir()
    frozen = run/'frozen'
    frozen.mkdir()
    for name in ['run.py', 'pins.json', 'oracle.json', 'config.toml']:
        shutil.copyfile(HERE/name, frozen/name)
    hashes = tree_hashes(frozen)
    save(run/'frozen-inputs.json', hashes)
    pins = json.loads((frozen/'pins.json').read_text())
    oracle = json.loads((frozen/'oracle.json').read_text())
    checks, cleanup, facts, active = {}, [], [], []
    result = {'schema_version': 1, 'component_id': 'ai-memory', 'scope': 'WSL2 Linux x86_64 synthetic 2.3.2 maintenance',
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'platform': {'system': platform.system(), 'release': platform.release(),
                           'architecture': platform.machine(), 'python': platform.python_version()},
              'pins': pins, 'frozen_inputs': hashes, 'checks': checks, 'cleanup': cleanup,
              'production_state_opened': False, 'production_promoted': False,
              'client_registration_changed': False, 'model_invocation': False,
              'os_confinement_established': False, 'whole_task_provider_usage': None,
              'backup': {'status': 'not_attempted'}, 'restore': {'status': 'not_attempted'}}
    env = {'HOME': os.environ['HOME'], 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(run/'tmp')}
    data, config = run/'data', frozen/'config.toml'

    def check(name, condition):
        if name in checks:
            raise ValueError('duplicate check')
        checks[name] = bool(condition)
        save(run/'receipt.partial.json', result)
        if not condition:
            raise AssertionError(name)

    def command(name, argv, extra_env=None):
        proc = subprocess.run(argv, cwd=run, env=env | (extra_env or {}),
                              capture_output=True, text=True, timeout=30)
        save(run/(name+'.command.private.json'), {'argv': argv, 'exit_code': proc.returncode,
                                                 'stdout': proc.stdout, 'stderr': proc.stderr})
        return proc

    def call(m, tool, project='alpha', **kw):
        arguments = {'workspace': oracle['workspace'], 'project': project, **kw}
        response = m.call(tool, **arguments)
        facts.append(selected_fact(m.name, tool, arguments, response))
        save(run/'native-facts.json', {'facts': facts})
        return response

    def start(name, store):
        m = MCP([str(binary), '--data-dir', str(store), '--config', str(config), 'serve',
                 '--transport', 'stdio', '--no-watcher', '--workspace', oracle['workspace'],
                 '--project', 'alpha'], run, env, run, name, cleanup)
        active.append(m)
        check(name+'_server_version', m.initialize()['serverInfo']['version'] == pins['version'])
        names = sorted(t['name'] for t in m.request('tools/list', {})['result']['tools'])
        result.setdefault('tool_names_by_phase', {})[name] = names
        check(name+'_required_tools', set(oracle['required_tools']).issubset(names))
        return m

    def stop(m):
        m.close()
        active.remove(m)

    def scopes(m, updated=False):
        for key in ['alpha', 'beta']:
            item = oracle['updated_alpha'] if key == 'alpha' and updated else oracle[key]
            path = oracle[key]['path']
            check(m.name+'_'+key+'_body', payload(call(m, 'memory_read_page', project=key, path=path))['body'] == item['body'])
            query = payload(call(m, 'memory_query', project=key, query=item['marker'], explain=True))
            check(m.name+'_'+key+'_fts', [h['path'] for h in query['hits']] == [path] and 'fts' in query['streams_active'])
            other = 'beta' if key == 'alpha' else 'alpha'
            check(m.name+'_'+key+'_negative_query', payload(call(m, 'memory_query', project=other, query=item['marker']))['hits'] == [])
            error = call(m, 'memory_read_page', project=other, path=path).get('error', {})
            check(m.name+'_'+key+'_negative_read', error.get('code') == -32603 and
                  'not found in resolved scope '+oracle['workspace']+'/'+other in error.get('message', ''))
        counts = payload(call(m, 'memory_status'))['counts']
        check(m.name+'_no_capture_status', counts['sessions'] == 0 and counts['observations'] == 0)
        if updated:
            item = oracle['unicode']
            check(m.name+'_unicode_exact_body', payload(call(m, 'memory_read_page', path=item['path']))['body'] == item['body'])
            q = payload(call(m, 'memory_query', query=item['marker'], explain=True))
            check(m.name+'_unicode_fts', [h['path'] for h in q['hits']] == [item['path']] and 'fts' in q['streams_active'])
            check(m.name+'_superseded_absent', payload(call(m, 'memory_query', query=oracle['alpha']['marker']))['hits'] == [])

    http = None
    http_files = []
    try:
        check('archive_sha256', sha(args.archive) == pins['archive_sha256'])
        check('sidecar_sha256', sha(args.sidecar) == pins['sidecar_sha256'])
        check('sidecar_agreement', args.sidecar.read_text().split()[0] == pins['archive_sha256'])
        dist = run/'dist'
        dist.mkdir()
        # Extract only the reviewed executable and license, never hooks/installers.
        with tarfile.open(args.archive) as tar:
            for name in ['ai-memory', 'LICENSE']:
                members = [m for m in tar.getmembers() if m.name in [name, './'+name]]
                if len(members) != 1 or not members[0].isfile():
                    raise ValueError('expected unique regular distribution file')
                with tar.extractfile(members[0]) as source:
                    (dist/name).write_bytes(source.read())
        binary = dist/'ai-memory'
        binary.chmod(0o700)
        check('binary_sha256', sha(binary) == pins['binary_sha256'])
        check('license_sha256', sha(dist/'LICENSE') == pins['license_sha256'])
        for name, argv in [('version', ['--version']), ('serve-help', ['serve', '--help']),
                           ('backup-help', ['backup', '--help']), ('restore-help', ['restore', '--help'])]:
            completed = command(name, [str(binary), *argv])
            result.setdefault('native_command_exits', {})[name] = completed.returncode
            check(name+'_exit', completed.returncode == 0)
            if name == 'version':
                check('native_version', completed.stdout.strip() == 'ai-memory '+pins['version'])
        m = start('fresh', data)
        for key in ['alpha', 'beta']:
            item = oracle[key]
            payload(call(m, 'memory_write_page', project=key, path=item['path'], body=item['body']))
        scopes(m)
        error = call(m, 'memory_write_page', path=oracle['reserved_path'], body='Synthetic rejected page.\n').get('error', {})
        check('git_reserved_path_rejected', error.get('code') == -32603 and 'is reserved by Git' in error.get('message', ''))
        item = oracle['unicode']
        payload(call(m, 'memory_write_page', path=item['path'], body=item['body']))
        check('unicode_exact_write_read', payload(call(m, 'memory_read_page', path=item['path']))['body'] == item['body'])
        payload(call(m, 'memory_write_page', path=oracle['alpha']['path'], body=oracle['updated_alpha']['body']))
        stop(m)
        m = start('restart', data)
        scopes(m, updated=True)
        stop(m)
        state = database_state(data)
        result['database_after_restart'] = state
        check('restart_integrity_and_v62', state['integrity'] == 'ok' and state['v62_present'] and state['missing_page_windows'] == 0)
        check('no_capture_or_embeddings_after_restart', not any(state['forbidden_population'].values()))
        # Reserve a presently unused loopback port. A bind race fails the owned
        # server; a per-run bearer prevents sending backup to an unrelated server.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        token = secrets.token_hex(32)
        http_env = {'AI_MEMORY_SERVER_URL': f'http://127.0.0.1:{port}', 'AI_MEMORY_AUTH_TOKEN': token}
        http_files = [(run/'backup-server.stdout').open('w'), (run/'backup-server.stderr').open('w')]
        http = subprocess.Popen([str(binary), '--data-dir', str(data), '--config', str(config),
            'serve', '--transport', 'http', '--bind', f'127.0.0.1:{port}', '--no-watcher',
            '--workspace', oracle['workspace'], '--project', 'alpha'], cwd=run, env=env | http_env,
            stdin=subprocess.DEVNULL, stdout=http_files[0], stderr=http_files[1])
        deadline = time.monotonic()+15
        while True:
            if http.poll() is not None:
                raise RuntimeError('owned HTTP server exited before readiness')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('owned HTTP readiness deadline')
                time.sleep(.05)
        backup = run/'native-backup.tar.gz'
        completed = command('backup', [str(binary), '--data-dir', str(data), '--config', str(config),
                                      'backup', '--to', str(backup)], http_env)
        result['backup'] = {'status': 'passed' if completed.returncode == 0 else 'failed',
                            'exit_code': completed.returncode, 'transport': 'owned authenticated loopback HTTP',
                            'archive_sha256': sha(backup) if backup.exists() else None}
        check('native_backup_exit', completed.returncode == 0 and backup.is_file())
        http.send_signal(2)
        http.wait(timeout=10)
        cleanup.append({'phase': 'backup-server', 'exit_code': http.returncode, 'forced_termination': False,
                        'shutdown': 'SIGINT to owned PID', 'owned_process_exited': True})
        http = None
        for stream in http_files:
            stream.close()
        http_files = []
        snapshot = run/'backup-snapshot'
        (snapshot/'db').mkdir(parents=True)
        with tarfile.open(backup) as tar:
            members = tar.getmembers()
            safe = all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
                       and (m.isfile() or m.isdir()) for m in members)
            check('native_backup_safe_entries', safe)
            matches = [m for m in members if m.name == 'db/memory.sqlite']
            check('native_backup_unique_database', len(matches) == 1 and matches[0].isfile())
            with tar.extractfile(matches[0]) as source:
                (snapshot/'db/memory.sqlite').write_bytes(source.read())
            archived_wiki = {m.name: hashlib.sha256(tar.extractfile(m).read()).hexdigest()
                             for m in members if m.isfile() and m.name.startswith('wiki/')}
            current_wiki = {'wiki/'+key: value for key, value in tree_hashes(data/'wiki').items()}
            check('native_backup_wiki_exact', archived_wiki == current_wiki)
        result['backup_database'] = database_state(snapshot)
        check('native_backup_database_integrity', result['backup_database'] == database_state(data))
        # No --force, process-name bypass, or sibling signals are permitted.
        restored = run/'restored'
        completed = command('restore', [str(binary), '--data-dir', str(restored), '--config', str(config),
                                       'restore', '--from', str(backup)])
        result['restore'] = {'status': 'failed', 'exit_code': completed.returncode}
        if completed.returncode != 0:
            blocked = bool(re.search(r'refusing to restore: [1-9][0-9]* other ai-memory process\(es\) running \(pids: \[[0-9, ]+\]\)', completed.stderr))
            result['restore']['status'] = 'blocked_by_native_sibling_process_guard' if blocked else 'failed'
            check('restore_refusal_matches_native_guard', blocked)
            check('restore_refusal_target_unchanged', not restored.exists())
        else:
            result['restore']['status'] = 'passed'
            m = start('restored', restored)
            scopes(m, updated=True)
            stop(m)
            state = database_state(restored)
            result['restored_database'] = state
            check('restored_integrity_and_v62', state['integrity'] == 'ok' and state['v62_present'] and state['missing_page_windows'] == 0)
            check('restored_capture_and_embedding_tables_empty', not any(state['forbidden_population'].values()))
        result['database_final'] = database_state(data)
        check('final_capture_and_embedding_tables_empty', not any(result['database_final']['forbidden_population'].values()))
        check('no_model_files', not any(p.is_file() for p in data.glob('models/**/*')))
        check('binary_unchanged', sha(binary) == pins['binary_sha256'])
        check('frozen_inputs_unchanged', hashes == tree_hashes(frozen))
        check('all_owned_processes_cleanly_exited', all(x['exit_code'] == 0 and not x['forced_termination'] and x['owned_process_exited'] and x.get('reader_closed', True) for x in cleanup))
        result['passed'] = True
    except Exception as exc:
        result.update(passed=False, failure={'type': type(exc).__name__, 'message': str(exc)})
    finally:
        for m in active:
            try:
                m.close()
            except Exception as exc:
                cleanup.append({'phase': m.name, 'cleanup_error': type(exc).__name__})
        if http is not None:
            try:
                if http.poll() is None:
                    http.terminate()
                    try:
                        http.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        http.kill()
                        http.wait(timeout=5)
                cleanup.append({'phase': 'backup-server', 'exit_code': http.returncode,
                                'forced_termination': True, 'owned_process_exited': http.poll() is not None})
            except Exception as exc:
                cleanup.append({'phase': 'backup-server', 'cleanup_error': type(exc).__name__})
        for stream in http_files:
            stream.close()
        result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['native_tool_calls'] = len(facts)
        result['private_log_hashes'] = {p.name: sha(p) for p in sorted(run.glob('*')) if p.is_file() and p.name not in ['receipt.json', 'receipt.partial.json']}
        save(run/'receipt.json', result)
        print(json.dumps({'passed': result.get('passed', False), 'checks': len(checks),
                          'failed_checks': [k for k,v in checks.items() if not v],
                          'native_tool_calls': len(facts), 'backup': result['backup']['status'],
                          'restore': result['restore']['status'], 'cleanup': cleanup}))
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
