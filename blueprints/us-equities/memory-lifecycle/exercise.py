"""Drive the installed ai-memory MCP server over its native stdio protocol.

Run only inside run.py's disposable namespace. Fixtures contain no user data.
"""
import datetime
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

ROOT = Path('/run')


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    if not Path('/ai-memory').is_file() or not (ROOT / 'config.toml').is_file():
        raise RuntimeError('use run.py to create the isolated environment')
    version = subprocess.check_output(['/ai-memory', '--version'], text=True).strip()
    save('version.json', {'version': version})
    argv = ['/ai-memory', '--data-dir', '/run/data', '--config', '/run/config.toml',
            'serve', '--transport', 'stdio', '--no-watcher',
            '--workspace', 'lifecycle', '--project', 'alpha']
    save('server-argv.json', argv)
    records = []
    save('namespace.json', {'network_namespace': str(Path('/proc/self/ns/net').readlink()),
                           'pid_namespace': str(Path('/proc/self/ns/pid').readlink()),
                           'home': str(Path.home()), 'environment_keys': sorted(__import__('os').environ),
                           'external_network_interfaces': [line.split(':')[0].strip() for line in
                               Path('/proc/net/dev').read_text().splitlines()[2:] if ':' in line]})
    (ROOT / 'mountinfo.txt').write_text(Path('/proc/self/mountinfo').read_text())
    with (ROOT / 'server.stderr').open('w') as err, (ROOT / 'protocol.jsonl').open('w') as log:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True)
        replies = queue.Queue()

        def read():
            try:
                for line in proc.stdout:
                    log.write(line)
                    log.flush()
                    replies.put(json.loads(line))
            except Exception as error:
                replies.put(error)
            finally:
                replies.put(EOFError('native stdio closed'))

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def request(method, params):
            identity = len(records) + 1
            message = {'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params}
            proc.stdin.write(json.dumps(message) + '\n')
            proc.stdin.flush()
            deadline = time.monotonic() + 15
            while True:
                response = replies.get(timeout=max(0.001, deadline - time.monotonic()))
                if isinstance(response, Exception):
                    raise response
                if response.get('id') == identity:
                    records.append({'request': message, 'response': response})
                    save('records.json', records)
                    return response
                if time.monotonic() > deadline:
                    raise TimeoutError('native MCP response deadline exceeded')

        outcomes = {}

        def call(label, tool, project='alpha', **arguments):
            if project is not None:
                arguments.update(workspace='lifecycle', project=project)
            outcomes[label] = request('tools/call', {'name': tool, 'arguments': arguments})
            save('outcomes.json', outcomes)

        try:
            initialized = request('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                  'clientInfo': {'name': 'disposable-lifecycle-acceptance', 'version': '1'}})
            if 'error' in initialized:
                raise RuntimeError('native initialize failed')
            proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
            proc.stdin.flush()
            save('tools.json', request('tools/list', {}))
            call('write_alpha', 'memory_write_page', path='notes/routing.md',
                 body='# Alpha routing\nCobaltquartz is an alpha fixture only.\n')
            call('write_beta', 'memory_write_page', project='beta', path='notes/routing.md',
                 body='# Beta routing\nAmbermeadow is a beta fixture only.\n')
            call('alpha_read', 'memory_read_page', path='notes/routing.md')
            call('beta_read', 'memory_read_page', project='beta', path='notes/routing.md')
            call('alpha_search_beta', 'memory_query', query='Ambermeadow')
            call('beta_search_alpha', 'memory_query', project='beta', query='Cobaltquartz')
            call('missing_scope', 'memory_read_page', project='absent', path='notes/routing.md')
            call('invalid_combined_scope', 'memory_query', query='Cobaltquartz', **{'global': True})
            call('write_expired', 'memory_write_page', path='notes/expired.md',
                 body='# Expired fixture\nVioletcedar is temporary.\n',
                 expires_at='2000-01-01T00:00:00Z', pinned=True)
            call('expired_default', 'memory_query', query='Violetcedar')
            call('expired_explicit', 'memory_query', query='Violetcedar', include_expired=True)
            call('expired_direct_read', 'memory_read_page', path='notes/expired.md')
            call('write_future', 'memory_write_page', path='notes/future.md',
                 body='# Future fixture\nSaffronwillow is retained.\n', expires_at='2999-01-01T00:00:00Z')
            call('future_default', 'memory_query', query='Saffronwillow')
            call('invalid_expiry', 'memory_write_page', path='notes/invalid-expiry.md',
                 body='# Invalid expiry\nAn invalid date should be rejected.\n', expires_at='not-a-date')
            call('write_old', 'memory_write_page', path='notes/revision.md',
                 body='# Revision fixture\nSilverorchard was the original selection.\n')
            # Select an instant strictly after the acknowledged write and before its replacement.
            time.sleep(0.05)
            instant = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save('as-of.json', {'instant': instant, 'semantics': 'ingestion time'})
            time.sleep(0.05)
            call('write_new', 'memory_write_page', path='notes/revision.md',
                 body='# Revision fixture\nGoldenharbor is the replacement selection.\n')
            call('old_now', 'memory_query', query='Silverorchard')
            call('new_now', 'memory_query', query='Goldenharbor')
            call('old_as_of', 'memory_query', query='Silverorchard', as_of=instant, explain=True)
            call('new_as_of', 'memory_query', query='Goldenharbor', as_of=instant, explain=True)
            call('sweep_preview', 'memory_forget_sweep', dry_run=True)
            call('expired_after_preview', 'memory_query', query='Violetcedar', include_expired=True)
            call('sweep_apply', 'memory_forget_sweep', dry_run=False)
            call('expired_after_sweep', 'memory_query', query='Violetcedar', include_expired=True)
            call('future_after_sweep', 'memory_query', query='Saffronwillow')
            call('delete_revision', 'memory_delete_page', path='notes/revision.md')
            call('deleted_now', 'memory_query', query='Goldenharbor')
            call('deleted_as_of', 'memory_query', query='Silverorchard', as_of=instant)
            call('beta_after_alpha_mutations', 'memory_read_page', project='beta', path='notes/routing.md')
            call('status', 'memory_status', project=None)
        finally:
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            save('shutdown.json', {'native_exit_code': proc.returncode})
            reader.join(timeout=2)
    print(json.dumps({'version': version, 'native_exit_code': proc.returncode,
                      'tool_calls': len(outcomes), 'protocol_requests': len(records)}))
    if proc.returncode:
        raise RuntimeError('native server failed')


if __name__ == '__main__':
    main()
