"""Drive the installed ai-memory MCP server over its native stdio protocol for the v2
lifecycle acceptance fixture (blueprints/memory-lifecycle-v2/PREREGISTRATION.md).

Run only inside run.py's disposable bubblewrap namespace. Fixtures contain no user data --
every project/workspace name and page body is an invented fixture term. Standard library
only, like v1 (blueprints/us-equities/memory-lifecycle/exercise.py), whose reader-thread /
timeout-queue pattern this reuses by attribution: run only inside a namespace that mounts
no real home, account or memory directory.

Two phases, selected by --phase:
  pre  -- fresh server against an empty --data-dir; the full 71-call fixture (routing across
          4 projects/2 workspaces, documented scopes/global search, a TTL crossing in real
          wall-clock time, a forget sweep followed by direct reads of both swept pages,
          v1-shape supersession/delete regressions, and a SECOND supersession pair left
          undeleted). Ends by writing a small handoff file (page ids + the captured as_of
          instants + expected bodies) to /run/handoff so a later, separate server process can
          check its own answers against them.
  post -- a NEW server process against the SAME --data-dir (the caller stops the "pre"
          process fully before starting this one). Reads the handoff file and performs only
          read-only verification calls (18 in all, including direct reads of the swept and
          deleted pages), plus one write+read-back to confirm the restarted process is fully
          live, not just serving frozen state.

Every request is retained with its label and wall-clock send/receive instants in
records.json (the full protocol exchange) and timeline.json (label -> instants), so the
real-time TTL ordering can be checked against the server's own reported expiry.
"""
import argparse
import datetime
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path('/run')
HANDOFF = ROOT / 'handoff' / 'fixture-state.json'

WS1 = 'lifecycle-v2'
WS2 = 'lifecycle-v2-secondary'
PROJECTS = {'alpha': WS1, 'beta': WS1, 'gamma': WS1, 'delta': WS2}
TERM = {
    'alpha': 'Marigoldpixel', 'beta': 'Driftwoodlantern', 'gamma': 'Cinderfoxglove',
    'delta': 'Thistlebronze',
    'expired_past': 'Palewinterlynx', 'future': 'Sablefernbrook',
    'revision_old': 'Hollowcopperfield', 'revision_new': 'Brightendersteel',
    'ttl_short': 'Emberquokka', 'durable': 'Granitewillow',
    'revision2_old': 'Ironpetalwren', 'revision2_new': 'Copperlatticefawn',
    'post_restart': 'Quillmarrowdrift',
}


def body_for(project):
    return f'# {project.capitalize()} routing\n{TERM[project]} is a {project} fixture only.\n'


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def rfc3339(dt):
    return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sleep_until(deadline):
    remaining = (deadline - now_utc()).total_seconds()
    if remaining > 0:
        time.sleep(remaining)


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


class Server:
    """One native stdio MCP server process: reader thread + id-matched reply queue,
    mirroring v1's proven pattern (a PIPE-backed stderr deadlocks; a file does not)."""

    def __init__(self, binary, data_dir, config, workspace, project):
        argv = [binary, '--data-dir', str(data_dir), '--config', str(config),
                'serve', '--transport', 'stdio', '--no-watcher',
                '--workspace', workspace, '--project', project]
        self.argv = argv
        self._stderr_file = open(ROOT / 'server.stderr', 'w')
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=self._stderr_file, text=True)
        self.replies = queue.Queue()
        self.records = []
        self._next_id = 0
        self._log = (ROOT / 'protocol.jsonl').open('w')
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                self._log.write(line)
                self._log.flush()
                self.replies.put(json.loads(line))
        except Exception as error:
            self.replies.put(error)
        finally:
            self.replies.put(EOFError('native stdio closed'))

    def request(self, method, params, label=None):
        self._next_id += 1
        ident = self._next_id
        message = {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params}
        sent = now_utc().isoformat()
        self.proc.stdin.write(json.dumps(message) + '\n')
        self.proc.stdin.flush()
        deadline = time.monotonic() + 15
        while True:
            response = self.replies.get(timeout=max(0.001, deadline - time.monotonic()))
            if isinstance(response, Exception):
                raise response
            if response.get('id') == ident:
                self.records.append({'label': label, 'sent_utc': sent,
                                     'received_utc': now_utc().isoformat(),
                                     'request': message, 'response': response})
                return response
            if time.monotonic() > deadline:
                raise TimeoutError('native MCP response deadline exceeded')

    def notify(self, method, params=None):
        self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': method,
                                          'params': params or {}}) + '\n')
        self.proc.stdin.flush()

    def initialize(self):
        initialized = self.request('initialize', {'protocolVersion': '2025-03-26',
            'capabilities': {}, 'clientInfo': {'name': 'memory-lifecycle-v2', 'version': '1'}})
        if 'error' in initialized:
            raise RuntimeError('native initialize failed')
        self.notify('notifications/initialized')
        return initialized

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self._reader.join(timeout=2)
        self._log.close()
        self._stderr_file.close()
        return self.proc.returncode


def make_call_fn(server, outcomes, timeline):
    def call(label, tool, scope, **arguments):
        """scope is a (workspace, project) pair, or None to omit both (for global=true,
        scopes=[...], and server-default calls)."""
        if label in outcomes:
            raise ValueError(f'duplicate fixture label {label}')
        if scope is not None:
            workspace, project = scope
            arguments = {**arguments, 'workspace': workspace, 'project': project}
        outcomes[label] = server.request('tools/call', {'name': tool, 'arguments': arguments}, label)
        record = server.records[-1]
        timeline[label] = {'sent_utc': record['sent_utc'], 'received_utc': record['received_utc']}
        save('outcomes.json', outcomes)
        save('timeline.json', timeline)
        return outcomes[label]
    return call


def payload(response):
    """Unwrap a successful tools/call response's single text-JSON content block. Raises on
    a protocol error or an isError result -- an expected-error check reads response directly
    and never calls this, so a call this DOES wrap is asserted to have actually succeeded."""
    if 'error' in response or response.get('result', {}).get('isError') is True:
        raise ValueError('native failure is not a successful empty result')
    content = response['result']['content']
    if len(content) != 1 or content[0]['type'] != 'text':
        raise ValueError('unexpected native content shape')
    value = json.loads(content[0]['text'])
    if not isinstance(value, dict):
        raise ValueError('expected native object')
    return value


def run_phase_pre(server):
    outcomes = {}
    call = make_call_fn(server, outcomes, {})
    alpha, beta, gamma, delta = (WS1, 'alpha'), (WS1, 'beta'), (WS1, 'gamma'), (WS2, 'delta')

    # Group R -- routing/isolation across 4 projects / 2 workspaces.
    for name, scope in [('alpha', alpha), ('beta', beta), ('gamma', gamma), ('delta', delta)]:
        call(f'write_{name}', 'memory_write_page', scope, path='notes/routing.md',
             body=body_for(name))
    for name, scope in [('alpha', alpha), ('beta', beta), ('gamma', gamma), ('delta', delta)]:
        call(f'{name}_read', 'memory_read_page', scope, path='notes/routing.md')
    for name, scope in [('alpha', alpha), ('beta', beta), ('gamma', gamma), ('delta', delta)]:
        call(f'{name}_search_self', 'memory_query', scope, query=TERM[name])
    scopes_by_name = {'alpha': alpha, 'beta': beta, 'gamma': gamma, 'delta': delta}
    for me in ('alpha', 'beta', 'gamma', 'delta'):
        for other in ('alpha', 'beta', 'gamma', 'delta'):
            if me == other:
                continue
            call(f'{me}_search_{other}', 'memory_query', scopes_by_name[me], query=TERM[other])
    call('missing_scope', 'memory_read_page', (WS1, 'absent'), path='notes/routing.md')
    call('invalid_combined_scope', 'memory_query', alpha, query=TERM['alpha'], **{'global': True})

    # Group G -- documented global/scopes behaviour.
    ws1_scopes = [{'workspace': WS1, 'project': p} for p in ('alpha', 'beta', 'gamma')]
    call('scopes_ws1_three', 'memory_query', None,
         query=f"{TERM['alpha']} OR {TERM['beta']} OR {TERM['gamma']}", scopes=ws1_scopes)
    call('scopes_excludes_delta', 'memory_query', None, query=TERM['delta'], scopes=ws1_scopes)
    for name in ('alpha', 'beta', 'gamma', 'delta'):
        call(f'global_finds_{name}', 'memory_query', None, query=TERM[name], **{'global': True})

    # Group T -- TTL crossing in real wall-clock time.
    expiry = now_utc() + datetime.timedelta(seconds=4)
    call('write_ttl_short', 'memory_write_page', alpha, path='notes/ttl-short.md',
         body=f"# TTL fixture\n{TERM['ttl_short']} expires soon.\n", expires_at=rfc3339(expiry))
    call('write_durable', 'memory_write_page', alpha, path='notes/durable.md',
         body=f"# Durable fixture\n{TERM['durable']} has no expiry.\n")
    call('ttl_before_expiry', 'memory_query', alpha, query=TERM['ttl_short'])
    sleep_until(expiry + datetime.timedelta(seconds=2.5))  # real time.sleep, not simulated
    call('ttl_after_expiry_default', 'memory_query', alpha, query=TERM['ttl_short'])
    call('ttl_after_expiry_explicit', 'memory_query', alpha, query=TERM['ttl_short'],
         include_expired=True)
    call('ttl_after_expiry_direct_read', 'memory_read_page', alpha, path='notes/ttl-short.md')
    call('durable_after_expiry_wait', 'memory_query', alpha, query=TERM['durable'])

    # Group V (part 1) -- v1-shape already-past-expiry+pinned and far-future regressions.
    call('write_expired_past', 'memory_write_page', alpha, path='notes/expired.md',
         body=f"# Expired fixture\n{TERM['expired_past']} is temporary.\n",
         expires_at='2000-01-01T00:00:00Z', pinned=True)
    call('expired_past_default', 'memory_query', alpha, query=TERM['expired_past'])
    call('expired_past_explicit', 'memory_query', alpha, query=TERM['expired_past'],
         include_expired=True)
    call('expired_past_direct_read', 'memory_read_page', alpha, path='notes/expired.md')
    call('write_future', 'memory_write_page', alpha, path='notes/future.md',
         body=f"# Future fixture\n{TERM['future']} is retained.\n", expires_at='2999-01-01T00:00:00Z')
    call('future_default', 'memory_query', alpha, query=TERM['future'])

    # Group S -- sweep, extended to cover BOTH expired pages.
    call('sweep_preview', 'memory_forget_sweep', alpha, dry_run=True)
    call('expired_past_after_preview', 'memory_query', alpha, query=TERM['expired_past'],
         include_expired=True)
    call('ttl_after_preview', 'memory_query', alpha, query=TERM['ttl_short'], include_expired=True)
    call('sweep_apply', 'memory_forget_sweep', alpha, dry_run=False)
    call('expired_past_after_sweep', 'memory_query', alpha, query=TERM['expired_past'],
         include_expired=True)
    call('ttl_after_sweep', 'memory_query', alpha, query=TERM['ttl_short'], include_expired=True)
    call('ttl_after_sweep_direct_read', 'memory_read_page', alpha, path='notes/ttl-short.md')
    call('expired_past_after_sweep_direct_read', 'memory_read_page', alpha, path='notes/expired.md')
    call('future_after_sweep', 'memory_query', alpha, query=TERM['future'])
    call('durable_after_sweep', 'memory_query', alpha, query=TERM['durable'])

    # Group V (part 2) -- invalid expiry, supersession/as_of, explicit delete.
    call('invalid_expiry', 'memory_write_page', alpha, path='notes/invalid-expiry.md',
         body='# Invalid expiry\nAn invalid date should be rejected.\n', expires_at='not-a-date')
    call('write_old', 'memory_write_page', alpha, path='notes/revision.md',
         body=f"# Revision fixture\n{TERM['revision_old']} is the original.\n")
    time.sleep(0.05)
    instant = now_utc().isoformat()
    time.sleep(0.05)
    call('write_new', 'memory_write_page', alpha, path='notes/revision.md',
         body=f"# Revision fixture\n{TERM['revision_new']} is the replacement.\n")
    call('old_now', 'memory_query', alpha, query=TERM['revision_old'])
    call('new_now', 'memory_query', alpha, query=TERM['revision_new'])
    call('old_as_of', 'memory_query', alpha, query=TERM['revision_old'], as_of=instant, explain=True)
    call('new_as_of', 'memory_query', alpha, query=TERM['revision_new'], as_of=instant, explain=True)
    call('delete_revision', 'memory_delete_page', alpha, path='notes/revision.md')
    call('deleted_now', 'memory_query', alpha, query=TERM['revision_new'])
    call('deleted_as_of', 'memory_query', alpha, query=TERM['revision_old'], as_of=instant)
    call('beta_after_alpha_mutations', 'memory_read_page', beta, path='notes/routing.md')

    # Group P -- a SECOND, undeleted supersession pair for the restart phase to re-check.
    call('write_old2', 'memory_write_page', alpha, path='notes/revision2.md',
         body=f"# Revision2 fixture\n{TERM['revision2_old']} is the original.\n")
    time.sleep(0.05)
    instant2 = now_utc().isoformat()
    time.sleep(0.05)
    call('write_new2', 'memory_write_page', alpha, path='notes/revision2.md',
         body=f"# Revision2 fixture\n{TERM['revision2_new']} is the replacement.\n")
    call('old2_as_of', 'memory_query', alpha, query=TERM['revision2_old'], as_of=instant2)
    call('new2_now', 'memory_query', alpha, query=TERM['revision2_new'])

    call('status_pre', 'memory_status', None)

    if len(outcomes) != 71:
        raise ValueError(f'expected exactly 71 phase-pre native tool calls, got {len(outcomes)}')

    old_id = payload(outcomes['write_old'])['page_id']
    new_id = payload(outcomes['write_new'])['page_id']
    old2_id = payload(outcomes['write_old2'])['page_id']
    new2_id = payload(outcomes['write_new2'])['page_id']
    handoff = {
        'instant': instant, 'instant2': instant2,
        'old_id': old_id, 'new_id': new_id, 'old2_id': old2_id, 'new2_id': new2_id,
        'bodies': {name: body_for(name) for name in PROJECTS},
        'status_pre_counts': payload(outcomes['status_pre'])['counts'],
    }
    HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    HANDOFF.write_text(json.dumps(handoff, indent=2, sort_keys=True) + '\n')
    return outcomes


def run_phase_post(server):
    handoff = json.loads(HANDOFF.read_text())
    outcomes = {}
    call = make_call_fn(server, outcomes, {})
    alpha, beta, gamma, delta = (WS1, 'alpha'), (WS1, 'beta'), (WS1, 'gamma'), (WS2, 'delta')

    for name, scope in [('alpha', alpha), ('beta', beta), ('gamma', gamma), ('delta', delta)]:
        call(f'{name}_read', 'memory_read_page', scope, path='notes/routing.md')
    call('durable_search', 'memory_query', alpha, query=TERM['durable'])
    call('old2_as_of', 'memory_query', alpha, query=TERM['revision2_old'],
         as_of=handoff['instant2'])
    call('new2_now', 'memory_query', alpha, query=TERM['revision2_new'])
    call('revision_deleted_current', 'memory_query', alpha, query=TERM['revision_new'])
    call('revision_deleted_as_of', 'memory_query', alpha, query=TERM['revision_old'],
         as_of=handoff['instant'])
    call('revision_deleted_direct_read', 'memory_read_page', alpha, path='notes/revision.md')
    call('ttl_short_gone', 'memory_query', alpha, query=TERM['ttl_short'], include_expired=True)
    call('expired_past_gone', 'memory_query', alpha, query=TERM['expired_past'], include_expired=True)
    call('ttl_short_direct_read_gone', 'memory_read_page', alpha, path='notes/ttl-short.md')
    call('expired_past_direct_read_gone', 'memory_read_page', alpha, path='notes/expired.md')
    call('future_present', 'memory_query', alpha, query=TERM['future'])
    call('status_post', 'memory_status', None)
    call('post_restart_write_readback', 'memory_write_page', alpha, path='notes/post-restart.md',
         body=f"# Post-restart fixture\n{TERM['post_restart']} was written after restart.\n")
    call('post_restart_readback_search', 'memory_query', alpha, query=TERM['post_restart'])

    if len(outcomes) != 18:
        raise ValueError(f'expected exactly 18 phase-post native tool calls, got {len(outcomes)}')
    return outcomes, handoff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['pre', 'post'])
    args = parser.parse_args()
    if not Path('/ai-memory').is_file() or not (ROOT / 'config.toml').is_file():
        raise RuntimeError('use run.py to create the isolated environment')

    version = subprocess.check_output(['/ai-memory', '--version'], text=True).strip()
    save('version.json', {'version': version, 'phase': args.phase})
    save('namespace.json', {'network_namespace': str(Path('/proc/self/ns/net').readlink()),
                            'pid_namespace': str(Path('/proc/self/ns/pid').readlink()),
                            'home': str(Path.home()), 'environment_keys': sorted(__import__('os').environ),
                            'external_network_interfaces': [line.split(':')[0].strip() for line in
                                Path('/proc/net/dev').read_text().splitlines()[2:] if ':' in line]})
    (ROOT / 'mountinfo.txt').write_text(Path('/proc/self/mountinfo').read_text())

    server = Server('/ai-memory', ROOT / 'data', ROOT / 'config.toml', WS1, 'alpha')
    save('server-argv.json', server.argv)
    try:
        server.initialize()
        save('tools.json', server.request('tools/list', {}))
        if args.phase == 'pre':
            outcomes = run_phase_pre(server)
            summary = {'version': version, 'phase': 'pre', 'tool_calls': len(outcomes)}
        else:
            outcomes, _handoff = run_phase_post(server)
            summary = {'version': version, 'phase': 'post', 'tool_calls': len(outcomes)}
    finally:
        save('records.json', server.records)
        exit_code = server.close()
        save('shutdown.json', {'native_exit_code': exit_code})
    summary['native_exit_code'] = exit_code
    summary['protocol_requests'] = len(server.records)
    print(json.dumps(summary))
    if exit_code:
        raise RuntimeError('native server failed')


if __name__ == '__main__':
    main()
