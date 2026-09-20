"""Offline consistency audit of the retained synthetic Linux native trial."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def audit(receipt, native, oracle, root=ROOT):
    """Check selected native results, not just the runner's pass booleans."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(receipt['passed'] is True and len(receipt['checks']) == 65
            and all(v is True for v in receipt['checks'].values()), 'all 65 native checks required')
    require(receipt['native_tool_calls'] == 39 and len(native['facts']) == 39, 'all native calls required')
    for field in ['production_state_opened', 'production_promoted', 'client_registration_changed',
                  'model_invocation', 'os_confinement_established']:
        require(receipt[field] is False, 'synthetic evidence cannot establish '+field)
    require(receipt['whole_task_provider_usage'] is None, 'whole-task usage remains unknown')
    require(receipt['platform']['system'] == 'Linux' and receipt['platform']['architecture'] == 'x86_64', 'wrong native platform')
    pins = json.loads((root/'pins.json').read_text())
    require(receipt['pins'] == pins and pins['version'] == '2.3.2', 'wrong distribution pin')
    require(set(receipt['frozen_inputs']) == {'run.py', 'pins.json', 'oracle.json', 'config.toml'}, 'all frozen inputs required')
    for name, expected in receipt['frozen_inputs'].items():
        require(hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, 'changed frozen input: '+name)
    require(receipt['native_command_exits'] == {'version': 0, 'serve-help': 0, 'backup-help': 0, 'restore-help': 0}, 'native preflight failure')
    require(receipt['backup']['status'] == 'passed' and receipt['backup']['exit_code'] == 0, 'native backup not accepted')
    require(receipt['backup']['archive_sha256'] == receipt['private_log_hashes']['native-backup.tar.gz'], 'backup hash mismatch')
    require(receipt['restore'] == {'status': 'passed', 'exit_code': 0}, 'restore not accepted')
    cleanup = receipt['cleanup']
    require([c['phase'] for c in cleanup] == ['fresh', 'restart', 'backup-server', 'restored'], 'all owned process exits required')
    for item in cleanup:
        require(item['exit_code'] == 0 and item['forced_termination'] is False
                and item['owned_process_exited'] is True, 'unclean owned exit')
        if item['phase'] != 'backup-server':
            require(item['reader_closed'] is True, 'stdio reader remains active')
        else:
            require(item['shutdown'] == 'SIGINT to owned PID', 'wrong HTTP shutdown scope')
    forbidden = ['sessions', 'observations', 'workstream_events', 'workstream_native_sessions', 'page_embeddings']
    for key in ['database_after_restart', 'backup_database', 'restored_database', 'database_final']:
        db = receipt[key]
        require(db['integrity'] == 'ok' and db['v62_present'] is True and db['missing_page_windows'] == 0
                and db['page_versions'] == 4, 'database integrity or page history mismatch')
        require(db['forbidden_population'] == dict.fromkeys(forbidden, 0), 'capture/embedding population appeared')
    toolsets = receipt['tool_names_by_phase']
    require(set(toolsets) == {'fresh', 'restart', 'restored'}, 'missing phase tool discovery')
    require(toolsets['fresh'] == toolsets['restart'] == toolsets['restored'], 'native tool discovery changed')
    require(set(oracle['required_tools']).issubset(toolsets['fresh']), 'required native tools missing')

    matched = set()

    def find(phase, tool, project='alpha', **args):
        wanted = dict(workspace=oracle['workspace'], project=project, **args)
        hits = [(i, fact) for i, fact in enumerate(native['facts']) if fact['phase'] == phase
                and fact['tool'] == tool and fact['arguments'] == wanted]
        require(len(hits) == 1, 'missing or duplicate native call')
        matched.add(hits[0][0])
        return hits[0][1]

    def value(fact):
        require('error' not in fact and 'tool_error' not in fact and 'value' in fact,
                'native error is not a successful empty result')
        return fact['value']

    def rejection(fact, reason):
        error = fact.get('error', {})
        require(error.get('code') == -32603 and reason in error.get('message', ''), 'wrong native rejection reason')

    for phase in ['fresh', 'restart', 'restored']:
        for key in ['alpha', 'beta']:
            item = oracle['updated_alpha'] if key == 'alpha' and phase != 'fresh' else oracle[key]
            path = oracle[key]['path']
            require(value(find(phase, 'memory_read_page', project=key, path=path))['body'] == item['body'], 'wrong exact scoped body')
            q = value(find(phase, 'memory_query', project=key, query=item['marker'], explain=True))
            require(q['hits'] == [{'path': path}] and 'fts' in q['streams_active'], 'wrong scoped FTS result')
            other = 'beta' if key == 'alpha' else 'alpha'
            require(value(find(phase, 'memory_query', project=other, query=item['marker']))['hits'] == [], 'cross-scope leakage')
            rejection(find(phase, 'memory_read_page', project=other, path=path),
                      'not found in resolved scope '+oracle['workspace']+'/'+other)
        require(value(find(phase, 'memory_status'))['counts'] == {'sessions': 0, 'observations': 0}, 'capture populated')
        if phase != 'fresh':
            item = oracle['unicode']
            require(value(find(phase, 'memory_read_page', path=item['path']))['body'] == item['body'], 'Unicode persistence failed')
            q = value(find(phase, 'memory_query', query=item['marker'], explain=True))
            require(q['hits'] == [{'path': item['path']}] and 'fts' in q['streams_active'], 'Unicode FTS failed')
            require(value(find(phase, 'memory_query', query=oracle['alpha']['marker']))['hits'] == [], 'old marker remains')
    for key in ['alpha', 'beta', 'unicode']:
        item = oracle[key]
        project = item.get('project', 'alpha')
        require(value(find('fresh', 'memory_write_page', project=project, path=item['path'], body=item['body'])) == {'acknowledged': True}, 'write failed')
    item = oracle['unicode']
    require(value(find('fresh', 'memory_read_page', path=item['path']))['body'] == item['body'], 'Unicode immediate read mismatch')
    require(value(find('fresh', 'memory_write_page', path=oracle['alpha']['path'], body=oracle['updated_alpha']['body'])) == {'acknowledged': True}, 'update failed')
    rejection(find('fresh', 'memory_write_page', path=oracle['reserved_path'], body='Synthetic rejected page.\n'), 'is reserved by Git')
    require(len(matched) == len(native['facts']), 'unassessed native calls')
    return {'evidence_consistent': True, 'native_checks': 65, 'native_tool_calls': len(matched),
            'synthetic_restart_backup_restore_accepted': True,
            'production_or_client_acceptance': False, 'whole_task_provider_usage': None}


if __name__ == '__main__':
    print(json.dumps(audit(json.loads((ROOT/'receipt.json').read_text()),
                           json.loads((ROOT/'native-facts.json').read_text()),
                           json.loads((ROOT/'oracle.json').read_text())), indent=2))
